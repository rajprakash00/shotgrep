"""Probe stage: read duration, fps, and codec with ffprobe.

The artifact is the same facts recorded as the stage's outputs in the manifest.
See pipeline/stages/__init__.py for the stage protocol.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from pipeline.errors import IngestError
from pipeline.jsonio import write_json

NAME = "probe"
ARTIFACT = "probe.json"
FFPROBE_TIMEOUT_S = 300


def run(source: Path, out_dir: Path) -> dict:
    probe = _ffprobe(source)
    facts = _facts(probe, source)
    write_json(Path(out_dir) / ARTIFACT, facts)
    return {"artifact": ARTIFACT, **facts}


def _ffprobe(source: Path) -> dict:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise IngestError("ffprobe not found on PATH; install FFmpeg")
    command = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(source),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=FFPROBE_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise IngestError(f"ffprobe timed out after {FFPROBE_TIMEOUT_S}s on {source.name}") from exc
    except OSError as exc:
        raise IngestError(f"could not run ffprobe: {exc}") from exc
    if completed.returncode != 0:
        lines = completed.stderr.strip().splitlines()
        detail = lines[-1] if lines else f"exit code {completed.returncode}"
        raise IngestError(f"ffprobe could not read {source.name}: {detail}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise IngestError(f"ffprobe returned invalid JSON for {source.name}") from exc


def _facts(probe: dict, source: Path) -> dict:
    video = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"), None)
    if video is None:
        raise IngestError(f"{source.name} has no video stream")
    codec = video.get("codec_name")
    if not codec:
        raise IngestError(f"{source.name}: ffprobe reported no video codec")
    return {
        "codec": codec,
        "duration_s": round(_duration_s(probe, video, source), 3),
        "fps": round(_frame_rate(video, source), 3),
    }


def _duration_s(probe: dict, video: dict, source: Path) -> float:
    raw = probe.get("format", {}).get("duration") or video.get("duration")
    if raw is None:
        raise IngestError(f"{source.name}: could not read duration")
    try:
        duration = float(raw)
    except (TypeError, ValueError) as exc:
        raise IngestError(f"{source.name}: could not read duration") from exc
    if duration <= 0:
        raise IngestError(f"{source.name}: non-positive duration {duration}")
    return duration


def _frame_rate(video: dict, source: Path) -> float:
    for key in ("avg_frame_rate", "r_frame_rate"):
        rate = _parse_rate(video.get(key))
        if rate is not None:
            return rate
    raise IngestError(f"{source.name}: could not read frame rate")


def _parse_rate(raw: object) -> float | None:
    numerator, _, denominator = str(raw or "").partition("/")
    try:
        rate = float(numerator) / float(denominator or 1)
    except (ValueError, ZeroDivisionError):
        return None
    return rate if rate > 0 else None
