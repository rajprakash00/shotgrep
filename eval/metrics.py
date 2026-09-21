"""Scoring for the eval harness: label matching, Recall@k, MRR, percentiles.

The harness compares systems on the same frozen labels. A result is relevant
when it comes from the labeled asset and its time range overlaps the expected
range expanded by the tolerance, so a moment returned a couple of seconds early
or late still counts. Recall@5 asks whether any relevant result appears in the
top five; MRR rewards how high the first relevant result ranks.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

DEFAULT_TOLERANCE_S = 2.0
RECALL_K = 5


@dataclass(frozen=True)
class Label:
    asset: str
    start_s: float
    end_s: float


def is_relevant(result: dict, label: Label, tolerance_s: float = DEFAULT_TOLERANCE_S) -> bool:
    if result["asset_id"] != label.asset:
        return False
    return result["start_s"] <= label.end_s + tolerance_s and result["end_s"] >= label.start_s - tolerance_s


def recall_at_k(relevance: Sequence[Sequence[bool]], k: int) -> float:
    if not relevance:
        raise ValueError("no queries to score")
    return sum(any(row[:k]) for row in relevance) / len(relevance)


def reciprocal_rank(relevance: Sequence[Sequence[bool]]) -> float:
    if not relevance:
        raise ValueError("no queries to score")
    return sum(_first_rank(row) for row in relevance) / len(relevance)


def _first_rank(row: Sequence[bool]) -> float:
    for rank, hit in enumerate(row, start=1):
        if hit:
            return 1.0 / rank
    return 0.0


@dataclass(frozen=True)
class Observation:
    """One query run through one system: its split, results, label, latency."""

    split: str
    label: Label
    results: list[dict]
    latency_ms: float


@dataclass(frozen=True)
class Metrics:
    n: int
    recall_at_5: float
    mrr: float
    p50_ms: float
    p95_ms: float


def percentile(values: Sequence[float], p: float) -> float:
    """Linear-interpolated percentile, the same convention as numpy default."""
    if not values:
        raise ValueError("no latencies to summarize")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * p / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower))


def score_by_split(
    observations: Sequence[Observation],
    *,
    k: int = RECALL_K,
    tolerance_s: float = DEFAULT_TOLERANCE_S,
) -> dict[str, Metrics]:
    """Metrics per split, plus an "overall" row over every observation."""
    if not observations:
        raise ValueError("no queries to score")
    groups: dict[str, list[Observation]] = {"overall": list(observations)}
    for observation in observations:
        groups.setdefault(observation.split, []).append(observation)
    return {split: _summarize(group, k, tolerance_s) for split, group in groups.items()}


def _summarize(observations: Sequence[Observation], k: int, tolerance_s: float) -> Metrics:
    relevance = [
        [is_relevant(result, observation.label, tolerance_s) for result in observation.results]
        for observation in observations
    ]
    latencies = [observation.latency_ms for observation in observations]
    return Metrics(
        n=len(observations),
        recall_at_5=recall_at_k(relevance, k),
        mrr=reciprocal_rank(relevance),
        p50_ms=percentile(latencies, 50),
        p95_ms=percentile(latencies, 95),
    )
