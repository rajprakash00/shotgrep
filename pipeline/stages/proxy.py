"""Proxy stage: a low-bitrate, browser-playable transcode for playback only.

Tries h264_nvenc when FFmpeg lists it and falls back to libx264 when the
hardware encode fails, so CPU-only machines stay correct. The output is H.264
in yuv420p with AAC audio and the moov atom first, which browsers can stream.
The manifest records which encoder produced the file. See
pipeline/stages/__init__.py for the stage protocol.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from pipeline.errors import IngestError

NAME = "proxy"
ARTIFACT = "proxy.mp4"
TEMPORARY = "proxy.partial.mp4"
HW_ENCODER = "h264_nvenc"
SW_ENCODER = "libx264"
MAX_WIDTH = 1280
SW_QUALITY = ["-preset", "veryfast", "-crf", "28"]
HW_QUALITY = ["-preset", "p4", "-cq", "28"]
TIMEOUT_S = 3600


def run(source: Path, out_dir: Path) -> dict:
    source = Path(source)
    out_dir = Path(out_dir)
    temp = out_dir / TEMPORARY
    ffmpeg = _ffmpeg()
    fallback_reason: str | None = None
    if _lists_encoder(ffmpeg, HW_ENCODER):
        try:
            _transcode(ffmpeg, source, temp, HW_ENCODER)
        except IngestError as exc:
            fallback_reason = str(exc)
        else:
            return _publish(temp, out_dir, HW_ENCODER)
    _transcode(ffmpeg, source, temp, SW_ENCODER)
    outputs = _publish(temp, out_dir, SW_ENCODER)
    if fallback_reason is not None:
        outputs["fallback_reason"] = fallback_reason
    return outputs


def _publish(temp: Path, out_dir: Path, encoder: str) -> dict:
    os.replace(temp, out_dir / ARTIFACT)
    return {"artifact": ARTIFACT, "encoder": encoder}


def _ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise IngestError("ffmpeg not found on PATH; install FFmpeg")
    return ffmpeg


def _lists_encoder(ffmpeg: str, encoder: str) -> bool:
    try:
        completed = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return any(encoder in line.split() for line in completed.stdout.splitlines())


def _transcode(ffmpeg: str, source: Path, dest: Path, encoder: str) -> None:
    quality = HW_QUALITY if encoder == HW_ENCODER else SW_QUALITY
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i",
        str(source),
        "-c:v",
        encoder,
        *quality,
        "-vf",
        f"scale='trunc(min({MAX_WIDTH},iw)/2)*2':-2",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-movflags",
        "+faststart",
        "-f",
        "mp4",
        str(dest),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise _encode_error(dest, f"ffmpeg timed out after {TIMEOUT_S}s encoding {source.name}") from exc
    except OSError as exc:
        raise _encode_error(dest, f"could not run ffmpeg: {exc}") from exc
    if completed.returncode != 0:
        detail = _stderr_tail(completed.stderr) or f"exit code {completed.returncode}"
        raise _encode_error(dest, f"ffmpeg ({encoder}) could not encode {source.name}: {detail}")


def _encode_error(dest: Path, message: str) -> IngestError:
    dest.unlink(missing_ok=True)
    return IngestError(message)


def _stderr_tail(stderr: str) -> str:
    lines = [line for line in stderr.splitlines() if line.strip()]
    return lines[-1] if lines else ""
