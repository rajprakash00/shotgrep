"""Frames stage: sample the asset's moments and store a JPEG thumbnail each.

Samples are the union of 1 fps, the first frame of every shot, and transcript
segment starts (the anchors). A sample carries every kind it fulfils; the
plain 1 fps kind is dropped where a shot or transcript sample already covers
the same time. Raw frames are never retained. Reads probe.json, shots.json,
and transcript.json. See pipeline/stages/__init__.py for the stage protocol.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import av
from PIL import Image

from pipeline.errors import IngestError
from pipeline.jsonio import read_json, write_json

NAME = "frames"
ARTIFACT = "frames.json"
THUMBNAILS = "thumbnails"
THUMBNAIL_WIDTH = 320
JPEG_QUALITY = 85
PROBE_ARTIFACT = "probe.json"
SHOTS_ARTIFACT = "shots.json"
TRANSCRIPT_ARTIFACT = "transcript.json"


@dataclass(frozen=True)
class Sample:
    time_ms: int
    kinds: tuple[str, ...]
    shot_index: int | None = None
    segment_index: int | None = None

    @property
    def time_s(self) -> float:
        return self.time_ms / 1000

    @property
    def thumbnail(self) -> str:
        return f"{THUMBNAILS}/{self.time_ms:08d}.jpg"


def run(source: Path, out_dir: Path) -> dict:
    source = Path(source)
    out_dir = Path(out_dir)
    probe = _artifact(out_dir, PROBE_ARTIFACT)
    shots = _artifact(out_dir, SHOTS_ARTIFACT)["shots"]
    segments = _artifact(out_dir, TRANSCRIPT_ARTIFACT)["segments"]
    samples = _plan(float(probe["duration_s"]), shots, segments)
    _extract(source, out_dir, samples, float(probe["fps"]))
    write_json(out_dir / ARTIFACT, {"fps": probe["fps"], "samples": [_as_json(sample) for sample in samples]})
    kinds = Counter(kind for sample in samples for kind in sample.kinds)
    return {"artifact": ARTIFACT, "count": len(samples), "kinds": dict(sorted(kinds.items()))}


def _plan(duration_s: float, shots: list[dict], segments: list[dict]) -> list[Sample]:
    fps_times = {second * 1000 for second in range(math.ceil(duration_s))}
    shot_starts: dict[int, int] = {}
    for shot in shots:
        shot_starts.setdefault(round(float(shot["start_s"]) * 1000), int(shot["index"]))
    anchors: dict[int, int] = {}
    for index, segment in enumerate(segments):
        anchors.setdefault(round(float(segment["start_s"]) * 1000), index)
    samples = []
    for time_ms in sorted(fps_times | shot_starts.keys() | anchors.keys()):
        kinds = []
        if time_ms in shot_starts:
            kinds.append("shot_start")
        if time_ms in anchors:
            kinds.append("transcript")
        if time_ms in fps_times and not kinds:
            kinds.append("frame")
        samples.append(Sample(time_ms, tuple(kinds), shot_starts.get(time_ms), anchors.get(time_ms)))
    return samples


def _extract(source: Path, out_dir: Path, samples: list[Sample], fps: float) -> None:
    thumbnail_dir = out_dir / THUMBNAILS
    thumbnail_dir.mkdir(parents=True, exist_ok=True)
    half_frame = 0.5 / fps if fps > 0 else 0.0
    pending = list(samples)
    last: av.VideoFrame | None = None
    try:
        with av.open(str(source)) as container:
            stream = container.streams.video[0]
            for frame in container.decode(stream):
                last = frame
                time_s = frame.time if frame.time is not None else float(frame.pts * stream.time_base)
                while pending and pending[0].time_s <= time_s + half_frame:
                    _save(frame, thumbnail_dir / Path(pending.pop(0).thumbnail).name)
    except av.error.FFmpegError as exc:
        raise IngestError(f"frame sampling could not read {source.name}: {exc}") from exc
    if pending and last is None:
        raise IngestError(f"frame sampling decoded no video from {source.name}")
    for sample in pending:
        _save(last, thumbnail_dir / Path(sample.thumbnail).name)


def _save(frame: av.VideoFrame, path: Path) -> None:
    image = frame.to_image()
    width = min(THUMBNAIL_WIDTH, image.width)
    height = max(1, round(image.height * width / image.width))
    image.resize((width, height), Image.BICUBIC).save(path, format="JPEG", quality=JPEG_QUALITY)


def _artifact(out_dir: Path, name: str) -> dict:
    path = out_dir / name
    if not path.is_file():
        raise IngestError(f"{name} is missing; run the earlier stages first")
    return read_json(path)


def _as_json(sample: Sample) -> dict:
    return {
        "kinds": list(sample.kinds),
        "segment_index": sample.segment_index,
        "shot_index": sample.shot_index,
        "thumbnail": sample.thumbnail,
        "time_s": sample.time_s,
    }
