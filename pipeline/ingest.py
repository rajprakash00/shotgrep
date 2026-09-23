"""Run the ordered stages over one asset and maintain its manifest.

The asset is identified by the SHA-256 of its bytes. The manifest lives at
work_dir/<asset-id>/manifest.json; completed stages are skipped, so reruns are
safe. --from-stage reruns from a chosen stage onward and leaves earlier stages
alone. A stage failure is recorded in the manifest before the error propagates.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from pathlib import Path

from pipeline.errors import IngestError
from pipeline.manifest import Manifest
from pipeline.stages import STAGES

CHUNK = 1 << 20
Progress = Callable[[str, int], None]


def ingest(
    source: Path,
    work_dir: Path,
    *,
    from_stage: str | None = None,
    progress: Progress | None = None,
) -> Manifest:
    source = _readable_file(Path(source))
    digest, size = _hash(source)
    asset = {
        "id": digest,
        "filename": source.name,
        "source_path": str(source),
        "bytes": size,
    }
    manifest = Manifest.load_or_create(Path(work_dir) / digest / "manifest.json", asset)
    asset_dir = manifest.path.parent
    names = [stage.NAME for stage in STAGES]
    start = _start_index(names, from_stage, manifest)
    if from_stage is not None:
        manifest.reset_from(names[start:])

    for position, stage in enumerate(STAGES):
        if position < start:
            continue
        if from_stage is None and manifest.stage_complete(stage.NAME):
            continue
        started = time.monotonic()
        try:
            outputs = stage.run(source, asset_dir)
        except IngestError as exc:
            manifest.record_failure(stage.NAME, str(exc), _elapsed_ms(started))
            manifest.set_status(manifest.overall_status(names))
            manifest.save()
            raise IngestError(f"{stage.NAME} stage failed: {exc}") from exc
        duration_ms = _elapsed_ms(started)
        manifest.record_success(stage.NAME, outputs, duration_ms)
        manifest.save()
        if progress is not None:
            progress(stage.NAME, duration_ms)

    manifest.set_status(manifest.overall_status(names))
    manifest.save()
    return manifest


def _start_index(names: list[str], from_stage: str | None, manifest: Manifest) -> int:
    if from_stage is None:
        return 0
    if from_stage not in names:
        raise IngestError(f"unknown stage {from_stage!r}; stages are {', '.join(names)}")
    start = names.index(from_stage)
    for name in names[:start]:
        if not manifest.stage_complete(name):
            raise IngestError(f"cannot start at stage {from_stage!r}: {name!r} is not complete")
    return start


def _readable_file(source: Path) -> Path:
    if not source.exists():
        raise IngestError(f"input not found: {source}")
    if not source.is_file():
        raise IngestError(f"input is not a file: {source}")
    return source.resolve()


def _hash(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(CHUNK), b""):
                size += len(chunk)
                digest.update(chunk)
    except OSError as exc:
        raise IngestError(f"cannot read input {path}: {exc}") from exc
    return digest.hexdigest(), size


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
