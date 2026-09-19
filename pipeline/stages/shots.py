"""Shots stage: detect shot boundaries with PySceneDetect.

Writes shots.json: contiguous, ordered ranges covering the whole asset. A clip
with no detected cuts is a single shot spanning the probe duration. See
pipeline/stages/__init__.py for the stage protocol.
"""

from __future__ import annotations

from pathlib import Path

from scenedetect import ContentDetector, FrameTimecode, VideoOpenFailure, detect

from pipeline.errors import IngestError
from pipeline.jsonio import read_json, write_json

NAME = "shots"
ARTIFACT = "shots.json"
PROBE_ARTIFACT = "probe.json"


def run(source: Path, out_dir: Path) -> dict:
    source = Path(source)
    out_dir = Path(out_dir)
    shots = [_shot(index, start.seconds, end.seconds) for index, (start, end) in enumerate(_scenes(source))]
    if not shots:
        shots = [_shot(0, 0.0, _probe_duration(out_dir, source))]
    write_json(out_dir / ARTIFACT, {"shots": shots})
    return {"artifact": ARTIFACT, "count": len(shots)}


def _scenes(source: Path) -> list[tuple[FrameTimecode, FrameTimecode]]:
    try:
        return detect(str(source), ContentDetector())
    except (VideoOpenFailure, OSError) as exc:
        raise IngestError(f"shot detection could not read {source.name}: {exc}") from exc


def _shot(index: int, start_s: float, end_s: float) -> dict:
    return {"index": index, "start_s": round(start_s, 3), "end_s": round(end_s, 3)}


def _probe_duration(out_dir: Path, source: Path) -> float:
    path = out_dir / PROBE_ARTIFACT
    if not path.is_file():
        raise IngestError(f"shot detection needs {path.name}; run the probe stage first")
    try:
        return float(read_json(path)["duration_s"])
    except (KeyError, TypeError, ValueError) as exc:
        raise IngestError(f"{path} has no readable duration_s; rerun the probe stage") from exc
