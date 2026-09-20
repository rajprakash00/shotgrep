"""ASR stage: record the asset's transcript with word-level timestamps.

The transcriber wrapper (pipeline/models/transcriber.py) owns model, precision,
and CUDA/CPU policy; this stage serializes the result and reports counts to the
manifest. See pipeline/stages/__init__.py for the stage protocol.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.jsonio import write_json
from pipeline.models.transcriber import FasterWhisperTranscriber

NAME = "asr"
ARTIFACT = "transcript.json"


def run(source: Path, out_dir: Path) -> dict:
    transcript = FasterWhisperTranscriber().transcribe(Path(source))
    artifact = transcript.as_artifact()
    write_json(Path(out_dir) / ARTIFACT, artifact)
    outputs = {
        "artifact": ARTIFACT,
        "compute_type": artifact["compute_type"],
        "device": transcript.device,
        "language": transcript.language,
        "model": transcript.model,
        "segments": len(transcript.segments),
        "words": len(transcript.words),
    }
    if transcript.fallback_reason is not None:
        outputs["fallback_reason"] = transcript.fallback_reason
    return outputs
