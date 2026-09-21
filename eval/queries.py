"""The frozen query set: labeled moments, difficulty splits, and its freeze.

`queries.yaml` is frozen once ranking work starts (docs/folder-structure.md).
The loader validates structure and vocabulary so a silent edit — an unknown
split, a duplicate id, an inverted range — fails loudly. A later ranking change
must not edit these labels; it appends a dated table to eval/RESULTS.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from eval.metrics import DEFAULT_TOLERANCE_S, Label

SPLITS = ("easy", "paraphrase", "temporal", "negation")
REQUIRED_FIELDS = ("id", "split", "text", "asset", "start_s", "end_s")


class QuerySetError(ValueError):
    """The frozen query set is malformed or was edited against the freeze rule."""


@dataclass(frozen=True)
class Query:
    id: str
    split: str
    text: str
    asset: str
    start_s: float
    end_s: float

    @property
    def label(self) -> Label:
        return Label(asset=self.asset, start_s=self.start_s, end_s=self.end_s)


@dataclass(frozen=True)
class QuerySet:
    version: int
    frozen_on: str
    tolerance_s: float
    queries: tuple[Query, ...]

    def of_split(self, split: str) -> tuple[Query, ...]:
        return tuple(query for query in self.queries if query.split == split)


def load_queries(path: Path) -> QuerySet:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise QuerySetError(f"could not read {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise QuerySetError(f"{path} must be a mapping with version, frozen_on, tolerance_s, queries")
    for field in ("version", "frozen_on", "tolerance_s", "queries"):
        if field not in raw:
            raise QuerySetError(f"{path} is missing {field!r}")
    entries = raw["queries"]
    if not isinstance(entries, list) or not entries:
        raise QuerySetError(f"{path} has no queries")
    queries = tuple(_query(path, index, entry) for index, entry in enumerate(entries))
    duplicates = _duplicates(query.id for query in queries)
    if duplicates:
        raise QuerySetError(f"{path} has duplicate ids: {', '.join(sorted(duplicates))}")
    return QuerySet(
        version=int(raw["version"]),
        frozen_on=str(raw["frozen_on"]),
        tolerance_s=float(raw.get("tolerance_s", DEFAULT_TOLERANCE_S)),
        queries=queries,
    )


def index_asset_ids(corpus_manifest: Path) -> dict[str, str]:
    """Map corpus manifest slugs to index asset ids (media content hashes).

    Labels name assets by their corpus slug for readability; the index keys
    assets by content hash, so the harness resolves one to the other here.
    """
    try:
        manifest = json.loads(Path(corpus_manifest).read_text(encoding="utf-8"))
        return {asset["id"]: asset["sha256"] for asset in manifest["assets"]}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise QuerySetError(f"could not read corpus manifest {corpus_manifest}: {exc}") from exc


def _query(path: Path, index: int, entry: object) -> Query:
    where = f"{path} query {index + 1}"
    if not isinstance(entry, dict):
        raise QuerySetError(f"{where} must be a mapping")
    missing = [field for field in REQUIRED_FIELDS if field not in entry]
    if missing:
        raise QuerySetError(f"{where} is missing {', '.join(missing)}")
    split = str(entry["split"])
    if split not in SPLITS:
        raise QuerySetError(f"{where} has unknown split {split!r}; splits are {', '.join(SPLITS)}")
    text = str(entry["text"]).strip()
    if not text:
        raise QuerySetError(f"{where} has empty text")
    start_s = float(entry["start_s"])
    end_s = float(entry["end_s"])
    if start_s > end_s:
        raise QuerySetError(f"{where} has start_s {start_s} after end_s {end_s}")
    return Query(
        id=str(entry["id"]),
        split=split,
        text=text,
        asset=str(entry["asset"]),
        start_s=start_s,
        end_s=end_s,
    )


def _duplicates(values) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates
