"""The per-asset manifest: the recovery contract for ingest.

Each stage records status, timing, outputs, and errors. Completed stages are
skipped on rerun and the manifest is only written when something changed, so a
no-op rerun leaves the file byte-identical.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from pipeline.errors import IngestError
from pipeline.jsonio import read_json, write_json

SCHEMA_VERSION = 1


class Manifest:
    def __init__(self, path: Path, data: dict, dirty: bool = False) -> None:
        self.path = path
        self.data = data
        self._dirty = dirty

    @classmethod
    def load_or_create(cls, path: Path, asset: dict) -> Manifest:
        path = Path(path)
        if path.is_file():
            try:
                data = read_json(path)
            except json.JSONDecodeError as exc:
                raise IngestError(f"{path} is not valid JSON ({exc}); delete it to re-ingest") from exc
            if data.get("schema_version") != SCHEMA_VERSION:
                raise IngestError(
                    f"{path} has schema_version {data.get('schema_version')!r}, "
                    f"this build understands {SCHEMA_VERSION}; delete it to re-ingest"
                )
            return cls(path, data)
        data = {
            "schema_version": SCHEMA_VERSION,
            "asset": asset,
            "status": "partial",
            "stages": {},
        }
        return cls(path, data, dirty=True)

    @property
    def status(self) -> str:
        return self.data["status"]

    def stage_entry(self, name: str) -> dict | None:
        return self.data["stages"].get(name)

    def stage_complete(self, name: str) -> bool:
        entry = self.stage_entry(name)
        return bool(entry and entry.get("status") == "complete")

    def overall_status(self, stage_names: Sequence[str]) -> str:
        entries = [self.stage_entry(name) for name in stage_names]
        if any(entry is not None and entry["status"] == "failed" for entry in entries):
            return "failed"
        if all(self.stage_complete(name) for name in stage_names):
            return "complete"
        return "partial"

    def reset_from(self, names: Sequence[str]) -> None:
        for name in names:
            if name in self.data["stages"]:
                del self.data["stages"][name]
                self._dirty = True

    def record_success(self, name: str, outputs: dict, duration_ms: int) -> None:
        self._record(name, "complete", outputs, None, duration_ms)

    def record_failure(self, name: str, error: str, duration_ms: int) -> None:
        self._record(name, "failed", {}, error, duration_ms)

    def _record(self, name: str, status: str, outputs: dict, error: str | None, duration_ms: int) -> None:
        self.data["stages"][name] = {
            "status": status,
            "duration_ms": duration_ms,
            "outputs": outputs,
            "error": error,
        }
        self._dirty = True

    def set_status(self, status: str) -> None:
        if self.data["status"] != status:
            self.data["status"] = status
            self._dirty = True

    def save(self) -> None:
        if not self._dirty:
            return
        write_json(self.path, self.data)
        self._dirty = False
