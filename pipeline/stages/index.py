"""Index stage: replace this asset's rows in the shared LanceDB index.

Reads frames.json, embeddings.npy, shots.json, transcript.json, probe.json,
and the asset's manifest. Rows for this asset are deleted and rewritten, so
rerunning is idempotent and other assets in the index are untouched. Every
moment records the embedding model, precision, and revision that produced it,
so a model change is a re-embed rather than a full re-ingest. See
pipeline/stages/__init__.py for the stage protocol.
"""

from __future__ import annotations

from pathlib import Path

import lancedb
import numpy as np
import pyarrow as pa

from pipeline.errors import IngestError
from pipeline.jsonio import read_json

NAME = "index"
INDEX_DIR = "index"
MOMENTS = "moments"
ASSETS = "assets"
INDEX_VERSION = 1
FRAMES_ARTIFACT = "frames.json"
EMBED_ARTIFACT = "embeddings.npy"
SHOTS_ARTIFACT = "shots.json"
TRANSCRIPT_ARTIFACT = "transcript.json"
PROBE_ARTIFACT = "probe.json"
MANIFEST = "manifest.json"

ASSET_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string(), nullable=False),
        pa.field("filename", pa.string(), nullable=False),
        pa.field("duration_s", pa.float64(), nullable=False),
        pa.field("fps", pa.float64(), nullable=False),
        pa.field("codec", pa.string(), nullable=False),
        pa.field("status", pa.string(), nullable=False),
        pa.field("index_version", pa.int32(), nullable=False),
    ]
)


def run(source: Path, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    frames = _artifact(out_dir, FRAMES_ARTIFACT)
    embeddings = _embeddings(out_dir)
    shots = _artifact(out_dir, SHOTS_ARTIFACT)["shots"]
    segments = _artifact(out_dir, TRANSCRIPT_ARTIFACT)["segments"]
    probe = _artifact(out_dir, PROBE_ARTIFACT)
    manifest = _artifact(out_dir, MANIFEST)
    embed = manifest["stages"]["embed"]["outputs"]
    asset = manifest["asset"]
    moments = _moments(frames["samples"], embeddings, shots, segments, asset, embed)
    _write(out_dir.parent / INDEX_DIR, asset, probe, moments, embeddings.shape[1])
    return {"index": INDEX_DIR, "moments": len(moments), "assets": 1}


def _moments(
    samples: list[dict],
    embeddings: np.ndarray,
    shots: list[dict],
    segments: list[dict],
    asset: dict,
    embed: dict,
) -> list[dict]:
    moments = []
    for index, sample in enumerate(samples):
        embedding = embeddings[index].tolist()
        time_ms = round(float(sample["time_s"]) * 1000)
        for kind in sample["kinds"]:
            start_s, end_s, shot_index, segment_index, snippet = _range(
                kind, sample, shots, segments
            )
            moments.append(
                {
                    "id": f"{asset['id']}-{kind}-{time_ms:08d}",
                    "asset_id": asset["id"],
                    "kind": kind,
                    "start_s": start_s,
                    "end_s": end_s,
                    "thumbnail": f"{asset['id']}/{sample['thumbnail']}",
                    "snippet": snippet,
                    "shot_index": shot_index,
                    "segment_index": segment_index,
                    "embedding": embedding,
                    "embedding_model": embed["model"],
                    "embedding_precision": embed["precision"],
                    "embedding_revision": embed["revision"],
                    "index_version": INDEX_VERSION,
                }
            )
    return moments


def _range(kind: str, sample: dict, shots: list[dict], segments: list[dict]) -> tuple:
    if kind == "shot_start":
        shot = shots[sample["shot_index"]]
        return float(shot["start_s"]), float(shot["end_s"]), int(sample["shot_index"]), None, None
    if kind == "transcript":
        segment = segments[sample["segment_index"]]
        return (
            float(segment["start_s"]),
            float(segment["end_s"]),
            sample["shot_index"],
            int(sample["segment_index"]),
            segment["text"],
        )
    time_s = float(sample["time_s"])
    return time_s, time_s, sample["shot_index"], None, None


def _write(index_dir: Path, asset: dict, probe: dict, moments: list[dict], dimension: int) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(index_dir))
    asset_row = {
        "id": asset["id"],
        "filename": asset["filename"],
        "duration_s": probe["duration_s"],
        "fps": probe["fps"],
        "codec": probe["codec"],
        "status": "indexed",
        "index_version": INDEX_VERSION,
    }
    existing = set(db.list_tables().tables)
    _upsert(db, ASSETS, ASSET_SCHEMA, "id", [asset_row], existing)
    _upsert(db, MOMENTS, _moment_schema(dimension), "asset_id", moments, existing)


def _upsert(db, name: str, schema: pa.Schema, key: str, rows: list[dict], existing: set[str]) -> None:
    table = pa.Table.from_pylist(rows, schema=schema)
    if name in existing:
        target = db.open_table(name)
        target.delete(f"{key} = '{rows[0][key]}'")
        target.add(table)
    else:
        db.create_table(name, data=table)


def _moment_schema(dimension: int) -> pa.Schema:
    return pa.schema(
        [
            pa.field("id", pa.string(), nullable=False),
            pa.field("asset_id", pa.string(), nullable=False),
            pa.field("kind", pa.string(), nullable=False),
            pa.field("start_s", pa.float64(), nullable=False),
            pa.field("end_s", pa.float64(), nullable=False),
            pa.field("thumbnail", pa.string(), nullable=False),
            pa.field("snippet", pa.string()),
            pa.field("shot_index", pa.int32()),
            pa.field("segment_index", pa.int32()),
            pa.field("embedding", pa.list_(pa.float32(), dimension), nullable=False),
            pa.field("embedding_model", pa.string(), nullable=False),
            pa.field("embedding_precision", pa.string(), nullable=False),
            pa.field("embedding_revision", pa.string(), nullable=False),
            pa.field("index_version", pa.int32(), nullable=False),
        ]
    )


def _embeddings(out_dir: Path) -> np.ndarray:
    path = out_dir / EMBED_ARTIFACT
    if not path.is_file():
        raise IngestError(f"{EMBED_ARTIFACT} is missing; run the embed stage first")
    return np.load(path)


def _artifact(out_dir: Path, name: str) -> dict:
    path = out_dir / name
    if not path.is_file():
        raise IngestError(f"{name} is missing; run the earlier stages first")
    return read_json(path)
