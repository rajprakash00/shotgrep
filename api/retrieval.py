"""Candidate retrieval: visual ANN and transcript keyword/fuzzy matching.

Visual moments are retrieved by cosine ANN over the query embedding, the same
model and precision that produced the index. Transcript moments are retrieved
lexically: tokens match exactly or fuzzily (difflib ratio), weighted by inverse
document frequency and normalized for segment length. A segment must cover at
least MIN_COVERAGE of the query's IDF weight, so sharing only stopwords with a
query does not put an irrelevant quote into the fused list. Both channels push
the same asset and time-range filters into LanceDB.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from math import log, log1p

FRAME = "frame"
SHOT_START = "shot_start"
TRANSCRIPT = "transcript"
VISUAL_KIND_CLAUSE = f"kind IN ({FRAME!r}, {SHOT_START!r})"
TRANSCRIPT_KIND_CLAUSE = f"kind = {TRANSCRIPT!r}"
FUZZY_THRESHOLD = 0.8
MIN_COVERAGE = 0.5
TOKEN_PATTERN = re.compile(r"[a-z0-9']+")


@dataclass(frozen=True)
class Hit:
    moment_id: str
    asset_id: str
    kind: str
    start_s: float
    end_s: float
    thumbnail: str
    snippet: str | None
    score: float


def as_hit(row: dict, score: float = 0.0) -> Hit:
    return Hit(
        moment_id=row["id"],
        asset_id=row["asset_id"],
        kind=row["kind"],
        start_s=float(row["start_s"]),
        end_s=float(row["end_s"]),
        thumbnail=row["thumbnail"],
        snippet=row["snippet"],
        score=float(score),
    )


def visual_hits(table, vector: list[float], where: str | None, limit: int) -> list[Hit]:
    query = table.search(vector).metric("cosine")
    if where is not None:
        query = query.where(where)
    rows = query.limit(limit).to_list()
    return [as_hit(row, 1.0 - float(row["_distance"])) for row in rows]


def transcript_hits(table, query: str, where: str | None, limit: int) -> list[Hit]:
    documents = _transcript_documents(table, where)
    scored = _score(query, documents)
    scored.sort(key=lambda hit: (-hit.score, hit.moment_id))
    return scored[:limit]


def filter_clause(asset: str | None, start_s: float | None, end_s: float | None) -> str | None:
    """An overlap filter: moments whose range intersects [start_s, end_s]."""
    clauses = []
    if asset:
        clauses.append(f"asset_id = {quote(asset)}")
    if start_s is not None:
        clauses.append(f"end_s >= {float(start_s)}")
    if end_s is not None:
        clauses.append(f"start_s <= {float(end_s)}")
    return where_clause(*clauses)


def where_clause(*clauses: str | None) -> str | None:
    present = [clause for clause in clauses if clause]
    return " AND ".join(present) if present else None


def quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _transcript_documents(table, where: str | None) -> list[tuple[dict, list[str]]]:
    query = table.search()
    if where is not None:
        query = query.where(where)
    query = query.select(["id", "asset_id", "kind", "start_s", "end_s", "thumbnail", "snippet"])
    return [(row, _tokens(row["snippet"] or "")) for row in query.to_list()]


def _score(query: str, documents: list[tuple[dict, list[str]]]) -> list[Hit]:
    query_tokens = sorted(set(_tokens(query)))
    if not query_tokens or not documents:
        return []
    document_frequency = Counter(token for _, tokens in documents for token in set(tokens))
    total = len(documents)
    hits = []
    for row, tokens in documents:
        score = _relevance(query_tokens, tokens, document_frequency, total)
        if score > 0.0:
            hits.append(as_hit(row, score))
    return hits


def _relevance(
    query_tokens: list[str],
    tokens: list[str],
    document_frequency: Counter,
    total: int,
) -> float:
    if not tokens:
        return 0.0
    unique = set(tokens)
    weights = {token: _idf(token, document_frequency, total) for token in query_tokens}
    total_weight = sum(weights.values())
    matched = 0.0
    for token, weight in weights.items():
        ratio = 1.0 if token in unique else _best_ratio(token, unique)
        if ratio >= FUZZY_THRESHOLD:
            matched += weight * ratio
    coverage = matched / total_weight
    if coverage < MIN_COVERAGE:
        return 0.0
    return coverage / (1.0 + log1p(len(tokens)))


def _idf(token: str, document_frequency: Counter, total: int) -> float:
    return log((total + 1) / (document_frequency.get(token, 0) + 1)) + 1.0


def _best_ratio(token: str, candidates: set[str]) -> float:
    return max((SequenceMatcher(None, token, candidate).ratio() for candidate in candidates), default=0.0)


def _tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())
