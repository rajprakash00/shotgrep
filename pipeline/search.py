"""First search: the moments nearest to a text query.

The query is embedded by the same SiglipOnnxEmbedder that produced the index,
and the index's recorded model, precision, and revision must match the query
embedder, so query and index vectors share one space. This is deliberately a
plain ANN lookup; fusion, keyword retrieval, priors, dedupe, deep links, and
URLs arrive with the query service. See pipeline/stages/index.py for the schema.
"""

from __future__ import annotations

from pathlib import Path

import lancedb

from pipeline.errors import IngestError
from pipeline.models.embedder import SiglipOnnxEmbedder
from pipeline.stages.index import INDEX_DIR, MOMENTS


def search(work_dir: Path, query: str, *, k: int = 5) -> dict:
    index_dir = Path(work_dir) / INDEX_DIR
    if not index_dir.is_dir():
        raise IngestError(f"no index at {index_dir}; run `shotgrep ingest` first")
    embedder = SiglipOnnxEmbedder()
    table = lancedb.connect(str(index_dir)).open_table(MOMENTS)
    _check_space(table, embedder)
    vector = embedder.embed_text(query)
    rows = table.search(vector).metric("cosine").limit(k).to_list()
    return {
        "query": query,
        "model": {
            "name": embedder.model,
            "precision": embedder.precision,
            "revision": embedder.revision,
        },
        "results": [_result(row) for row in rows],
    }


def _check_space(table, embedder: SiglipOnnxEmbedder) -> None:
    mismatched = table.count_rows(
        f"embedding_model != '{embedder.model}' "
        f"OR embedding_precision != '{embedder.precision}' "
        f"OR embedding_revision != '{embedder.revision}'"
    )
    if mismatched:
        raise IngestError(
            f"the index holds {mismatched} moments embedded by another model or precision; "
            "re-ingest or match SHOTGREP_EMBED_MODEL and SHOTGREP_EMBED_PRECISION"
        )


def _result(row: dict) -> dict:
    return {
        "moment_id": row["id"],
        "asset_id": row["asset_id"],
        "kind": row["kind"],
        "start_s": row["start_s"],
        "end_s": row["end_s"],
        "thumbnail": row["thumbnail"],
        "snippet": row["snippet"],
        "score": round(1.0 - float(row["_distance"]), 6),
    }
