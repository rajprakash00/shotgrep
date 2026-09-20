"""Speech to text with word timestamps, behind one interface.

FasterWhisperTranscriber hides the runtime: model and precision are chosen
here, CUDA is used when a device is present, and a failed CUDA attempt falls
back to the CPU path with the reason recorded. Assets without an audio stream
transcribe to an empty Transcript with device "none". Swapping model or
precision means editing this module; the asr stage does not change.
"""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import av
import ctranslate2

from pipeline.errors import IngestError

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

MODEL_ENV = "SHOTGREP_ASR_MODEL"
DEVICE_ENV = "SHOTGREP_ASR_DEVICE"
DEFAULT_MODEL = "large-v3"
COMPUTE_TYPE = "int8"
AUTO = "auto"
CPU = "cpu"
CUDA = "cuda"
NO_AUDIO = "none"
DEVICES = (AUTO, CPU, CUDA)


@dataclass(frozen=True)
class Word:
    text: str
    start_s: float
    end_s: float


@dataclass(frozen=True)
class Segment:
    text: str
    start_s: float
    end_s: float
    words: tuple[Word, ...]


@dataclass(frozen=True)
class Transcript:
    """A word-timestamped transcript; `device` names the path that produced it."""

    model: str
    device: str
    language: str | None
    language_probability: float | None
    segments: tuple[Segment, ...]
    fallback_reason: str | None = None

    @property
    def words(self) -> tuple[Word, ...]:
        return tuple(word for segment in self.segments for word in segment.words)

    def as_artifact(self) -> dict:
        return {
            "compute_type": COMPUTE_TYPE,
            "device": self.device,
            "language": self.language,
            "language_probability": self.language_probability,
            "model": self.model,
            "segments": [
                {
                    "end_s": segment.end_s,
                    "start_s": segment.start_s,
                    "text": segment.text,
                    "words": [
                        {"end_s": word.end_s, "start_s": word.start_s, "word": word.text}
                        for word in segment.words
                    ],
                }
                for segment in self.segments
            ],
        }


class Transcriber(Protocol):
    def transcribe(self, source: Path) -> Transcript: ...


class FasterWhisperTranscriber:
    """faster-whisper with int8 compute: CUDA when present, CPU otherwise."""

    def __init__(self, model: str | None = None, device: str | None = None) -> None:
        self.model = model or os.environ.get(MODEL_ENV) or DEFAULT_MODEL
        self.device = _requested_device(device or os.environ.get(DEVICE_ENV))

    def transcribe(self, source: Path) -> Transcript:
        source = Path(source)
        if not _has_audio(source):
            return Transcript(self.model, NO_AUDIO, None, None, ())
        if self.device == CPU or (self.device == AUTO and not _cuda_present()):
            return self._recognize(source, CPU)
        try:
            return self._recognize(source, CUDA)
        except IngestError as exc:
            return replace(self._recognize(source, CPU), fallback_reason=str(exc))

    def _recognize(self, source: Path, device: str) -> Transcript:
        model = _load_model(self.model, device)
        try:
            raw_segments, info = model.transcribe(str(source), word_timestamps=True)
            segments = tuple(_segment(segment) for segment in raw_segments)
        except Exception as exc:
            raise IngestError(f"transcription failed on {source.name}: {exc}") from exc
        probability = round(float(info.language_probability), 3) if info.language_probability is not None else None
        return Transcript(self.model, device, info.language or None, probability, segments)


def _load_model(model_name: str, device: str) -> WhisperModel:
    if device == CUDA:
        _preload_cuda_libraries()
    try:
        from faster_whisper import WhisperModel

        return WhisperModel(model_name, device=device, compute_type=COMPUTE_TYPE)
    except Exception as exc:
        raise IngestError(f"could not load ASR model {model_name!r} on {device}: {exc}") from exc


def _preload_cuda_libraries() -> None:
    """Load pip-wheel cuBLAS so ctranslate2's dlopen can resolve it.

    nvidia-cublas-cu12 ships the library under site-packages/nvidia/cublas/lib,
    which is not on the dynamic loader path. Loading it by absolute path first
    makes the bare soname resolvable. No-op when the wheel is not installed.
    """
    try:
        import nvidia.cublas.lib as cublas_lib
    except ImportError:
        return
    lib_dir = Path(cublas_lib.__path__[0])
    for name in ("libcublasLt.so.12", "libcublas.so.12"):
        library = lib_dir / name
        if library.is_file():
            ctypes.CDLL(str(library), mode=ctypes.RTLD_GLOBAL)


def _segment(segment) -> Segment:
    return Segment(
        text=segment.text.strip(),
        start_s=_seconds(segment.start),
        end_s=_seconds(segment.end),
        words=tuple(_word(word) for word in segment.words or []),
    )


def _word(word) -> Word:
    return Word(text=word.word.strip(), start_s=_seconds(word.start), end_s=_seconds(word.end))


def _seconds(value: float) -> float:
    return round(float(value), 3)


def _has_audio(source: Path) -> bool:
    try:
        with av.open(str(source)) as container:
            return any(stream.type == "audio" for stream in container.streams)
    except (av.error.FFmpegError, OSError, ValueError) as exc:
        raise IngestError(f"could not read {source.name}: {exc}") from exc


def _requested_device(value: str | None) -> str:
    device = (value or AUTO).strip().lower()
    if device not in DEVICES:
        raise IngestError(f"{DEVICE_ENV} must be one of {', '.join(DEVICES)}, got {device!r}")
    return device


def _cuda_present() -> bool:
    return ctranslate2.get_cuda_device_count() > 0
