"""The query service: one interface behind REST and MCP.

Search fuses visual ANN with dense and lexical transcript retrieval, normalizes
scores, applies a shot-start prior, and collapses near-duplicate moments. The
visual and text embedding spaces are validated channel by channel, so a query
embedder that does not match what the index stored is refused. Moment lookup
and transcript range reads come from the same index, so the deployed artifact
is the built index alone. Thumbnails are returned as public URLs and every
result carries a deep link into the web player. Handlers in api/app.py
translate this interface to HTTP; api/mcp_server.py translates the same
interface to MCP tools.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import lancedb

from api.fusion import fuse
from api.retrieval import (
    TRANSCRIPT_KIND_CLAUSE,
    VISUAL_KIND_CLAUSE,
    Hit,
    as_hit,
    dense_transcript_hits,
    filter_clause,
    quote,
    transcript_hits,
    visual_hits,
    where_clause,
)
from pipeline.errors import IngestError
from pipeline.stages.index import ASSETS, INDEX_VERSION, MOMENTS, TRANSCRIPTS

if TYPE_CHECKING:
    from pipeline.models.embedder import SiglipOnnxEmbedder
    from pipeline.models.text_embedder import TextOnnxEmbedder

API_URL_ENV = "SHOTGREP_API_URL"
WEB_URL_ENV = "SHOTGREP_WEB_URL"
DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_WEB_URL = "http://localhost:3000"
DEFAULT_K = 10
MAX_K = 100
# A fixed candidate window per channel: the ranked list a query produces does
# not change with k, so requesting more results appends rather than reshuffles.
CANDIDATE_LIMIT = 200


class NotFoundError(LookupError):
    """A moment or asset id that is not in the index."""


class QueryService:
    """Reads one built index: search, moment lookup, transcript ranges."""

    def __init__(
        self,
        index_dir: Path,
        *,
        embedder: SiglipOnnxEmbedder | None = None,
        text_embedder: TextOnnxEmbedder | None = None,
        api_url: str | None = None,
        web_url: str | None = None,
    ) -> None:
        self.index_dir = Path(index_dir)
        self.api_url = (api_url or os.environ.get(API_URL_ENV) or DEFAULT_API_URL).rstrip("/")
        self.web_url = (web_url or os.environ.get(WEB_URL_ENV) or DEFAULT_WEB_URL).rstrip("/")
        self._embedder = embedder
        self._text_embedder = text_embedder
        self._db = None
        self._ready = False

    def search(
        self,
        query: str,
        *,
        k: int = DEFAULT_K,
        asset: str | None = None,
        start_s: float | None = None,
        end_s: float | None = None,
    ) -> dict:
        if k <= 0:
            raise ValueError("k must be positive")
        self._prepare_tables()
        embedder = self._get_embedder()
        text_embedder = self._get_text_embedder()
        self._check_embedding_space(embedder, text_embedder)
        filters = filter_clause(asset, start_s, end_s)
        visual = visual_hits(
            self._table(MOMENTS),
            self._vector(query),
            where_clause(VISUAL_KIND_CLAUSE, filters),
            CANDIDATE_LIMIT,
        )
        dense = dense_transcript_hits(
            self._table(MOMENTS),
            self._text_vector(query),
            where_clause(TRANSCRIPT_KIND_CLAUSE, filters),
            CANDIDATE_LIMIT,
        )
        transcript = transcript_hits(
            self._table(MOMENTS),
            query,
            where_clause(TRANSCRIPT_KIND_CLAUSE, filters),
            CANDIDATE_LIMIT,
        )
        results = fuse([visual, dense, transcript], k)
        return {
            "query": query,
            "model": self._model(),
            "results": [self._result(row.hit, row.score) for row in results],
        }

    def moment(self, moment_id: str) -> dict:
        self._prepare_tables()
        rows = self._table(MOMENTS).search().where(f"id = {quote(moment_id)}").limit(1).to_list()
        if not rows:
            raise NotFoundError(f"no moment {moment_id!r} in the index")
        return self._result(as_hit(rows[0]), None)

    def asset(self, asset_id: str) -> dict:
        """Asset metadata plus the public URL of its playback proxy."""
        self._prepare_tables()
        return self._asset_payload(self._asset(asset_id))

    def list_assets(self) -> dict:
        """Every indexed asset, ordered by filename so listings are stable."""
        self._prepare_tables()
        rows = self._table(ASSETS).search().to_list()
        rows.sort(key=lambda row: (row["filename"], row["id"]))
        return {"assets": [self._asset_payload(row) for row in rows]}

    def transcript(
        self,
        asset_id: str,
        *,
        start_s: float | None = None,
        end_s: float | None = None,
    ) -> dict:
        self._prepare_tables()
        asset = self._asset(asset_id)
        start = 0.0 if start_s is None else float(start_s)
        end = float(asset["duration_s"]) if end_s is None else float(end_s)
        rows = self._table(TRANSCRIPTS).search().where(filter_clause(asset_id, start, end)).to_list()
        rows.sort(key=lambda row: row["segment_index"])
        return {
            "asset_id": asset_id,
            "start_s": start,
            "end_s": end,
            "segments": [_segment(row) for row in rows],
        }

    def _prepare_tables(self) -> None:
        """Open the index once; lookups need no embedding model, so this is all they check."""
        if self._ready:
            return
        if not self.index_dir.is_dir():
            raise IngestError(f"no index at {self.index_dir}; run `shotgrep ingest` first")
        self._db = lancedb.connect(str(self.index_dir))
        names = set(self._db.list_tables().tables)
        missing = [name for name in (MOMENTS, ASSETS, TRANSCRIPTS) if name not in names]
        if missing:
            raise IngestError(
                f"the index at {self.index_dir} has no {', '.join(missing)} table; re-ingest"
            )
        stale = self._table(MOMENTS).count_rows(f"index_version != {INDEX_VERSION}")
        if stale:
            raise IngestError(
                f"the index holds {stale} moments built by another shotgrep version; re-ingest"
            )
        self._ready = True

    def _check_embedding_space(
        self, embedder: SiglipOnnxEmbedder, text_embedder: TextOnnxEmbedder
    ) -> None:
        mismatched = self._table(MOMENTS).count_rows(
            f"embedding_model != {quote(embedder.model)} "
            f"OR embedding_precision != {quote(embedder.precision)} "
            f"OR embedding_revision != {quote(embedder.revision)}"
        )
        if mismatched:
            raise IngestError(
                f"the index holds {mismatched} moments embedded by another model or precision; "
                "re-ingest or match SHOTGREP_EMBED_MODEL and SHOTGREP_EMBED_PRECISION"
            )
        mismatched_transcript = self._table(MOMENTS).count_rows(
            f"{TRANSCRIPT_KIND_CLAUSE} AND ("
            f"text_embedding_model != {quote(text_embedder.model)} "
            f"OR text_embedding_precision != {quote(text_embedder.precision)} "
            f"OR text_embedding_revision != {quote(text_embedder.revision)} "
            f"OR text_embedding_model IS NULL)"
        )
        if mismatched_transcript:
            raise IngestError(
                f"the index holds {mismatched_transcript} transcript moments embedded by another "
                "text model or precision; re-ingest or match SHOTGREP_TEXT_EMBED_MODEL and "
                "SHOTGREP_TEXT_EMBED_PRECISION"
            )

    def _table(self, name: str):
        return self._db.open_table(name)

    def _get_embedder(self) -> SiglipOnnxEmbedder:
        if self._embedder is None:
            from pipeline.models.embedder import SiglipOnnxEmbedder

            self._embedder = SiglipOnnxEmbedder()
        return self._embedder

    def _get_text_embedder(self) -> TextOnnxEmbedder:
        if self._text_embedder is None:
            from pipeline.models.text_embedder import TextOnnxEmbedder

            self._text_embedder = TextOnnxEmbedder()
        return self._text_embedder

    def _vector(self, query: str) -> list[float]:
        return self._get_embedder().embed_text(query).tolist()

    def _text_vector(self, query: str) -> list[float]:
        return self._get_text_embedder().embed_query(query).tolist()

    def _model(self) -> dict:
        embedder = self._get_embedder()
        return {
            "name": embedder.model,
            "precision": embedder.precision,
            "revision": embedder.revision,
        }

    def _asset(self, asset_id: str) -> dict:
        rows = self._table(ASSETS).search().where(f"id = {quote(asset_id)}").limit(1).to_list()
        if not rows:
            raise NotFoundError(f"no asset {asset_id!r} in the index")
        return rows[0]

    def _asset_payload(self, row: dict) -> dict:
        return {
            "asset_id": row["id"],
            "filename": row["filename"],
            "duration_s": float(row["duration_s"]),
            "fps": float(row["fps"]),
            "codec": row["codec"],
            "status": row["status"],
            "proxy_url": self._media_url(f"{row['id']}/proxy.mp4"),
        }

    def _result(self, hit: Hit, score: float | None) -> dict:
        return {
            "moment_id": hit.moment_id,
            "asset_id": hit.asset_id,
            "kind": hit.kind,
            "start_s": hit.start_s,
            "end_s": hit.end_s,
            "thumbnail_url": self._media_url(hit.thumbnail),
            "snippet": hit.snippet,
            "score": score if score is None else round(score, 6),
            "deep_link": self._deep_link(hit),
        }

    def _media_url(self, relative_path: str) -> str:
        return f"{self.api_url}/media/{relative_path}"

    def _deep_link(self, hit: Hit) -> str:
        return f"{self.web_url}/watch/{hit.asset_id}?t={_timestamp(hit.start_s)}"


def _segment(row: dict) -> dict:
    return {
        "text": row["text"],
        "start_s": float(row["start_s"]),
        "end_s": float(row["end_s"]),
        "words": [
            {"word": word["word"], "start_s": float(word["start_s"]), "end_s": float(word["end_s"])}
            for word in row["words"] or []
        ],
    }


def _timestamp(seconds: float) -> str:
    return f"{seconds:.3f}".rstrip("0").rstrip(".")
