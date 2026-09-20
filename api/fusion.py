"""Score normalization, reciprocal rank fusion, priors, and dedupe.

Each retrieval channel contributes a ranked list. Raw scores are normalized
per channel against the channel's best (score / max), then each candidate
contributes its normalized score divided by its rank offset: a weighted
reciprocal rank fusion. Normalizing against the maximum keeps the ordering
independent of the candidate window's size, and the rank denominator makes a
channel's consensus matter as much as its raw confidence. Shot starts get a
prior so they rank above mid-shot samples that look alike, and a greedy
collapse drops near-duplicate moments (same asset, same kind, within
DEDUPE_WINDOW_S) so adjacent 1 fps samples cannot fill the list. Final scores
are relative to the best result: the top one is 1.0.
"""

from __future__ import annotations

from dataclasses import dataclass

from api.retrieval import SHOT_START, Hit

RRF_K = 60
SHOT_START_PRIOR = 0.15
DEDUPE_WINDOW_S = 1.5


@dataclass(frozen=True)
class Ranked:
    hit: Hit
    score: float


def fuse(channels: list[list[Hit]], limit: int) -> list[Ranked]:
    if limit <= 0:
        return []
    entries: dict[str, dict] = {}
    for channel in channels:
        if not channel:
            continue
        for rank, (hit, normalized) in enumerate(zip(channel, _normalized(channel), strict=True)):
            entry = entries.setdefault(hit.moment_id, {"hit": hit, "score": 0.0})
            entry["score"] += normalized / (RRF_K + rank + 1)
    if not entries:
        return []
    for entry in entries.values():
        if entry["hit"].kind == SHOT_START:
            entry["score"] *= 1.0 + SHOT_START_PRIOR
    ordered = sorted(entries.values(), key=lambda entry: (-entry["score"], entry["hit"].moment_id))
    best = ordered[0]["score"] or 1.0
    return _collapse([Ranked(entry["hit"], entry["score"] / best) for entry in ordered], limit)


def _normalized(channel: list[Hit]) -> list[float]:
    best = max(hit.score for hit in channel)
    if best <= 0.0:
        return [0.0] * len(channel)
    return [max(0.0, hit.score) / best for hit in channel]


def _collapse(ranked: list[Ranked], limit: int) -> list[Ranked]:
    kept: list[Ranked] = []
    for row in ranked:
        duplicate = any(
            row.hit.asset_id == other.hit.asset_id
            and row.hit.kind == other.hit.kind
            and abs(row.hit.start_s - other.hit.start_s) < DEDUPE_WINDOW_S
            for other in kept
        )
        if duplicate:
            continue
        kept.append(row)
        if len(kept) == limit:
            break
    return kept
