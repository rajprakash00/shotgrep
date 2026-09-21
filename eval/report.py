"""Render an eval run as the markdown table committed to eval/RESULTS.md.

One dated section per run; the freeze note pins the query set, corpus, and
index with hashes, and states the rule plainly: later ranking changes append a
new dated table instead of editing the labels. The renderer is pure so the
committed table can be regenerated deterministically from a Report.
"""

from __future__ import annotations

from dataclasses import dataclass

from eval.metrics import Metrics
from eval.queries import SPLITS

TABLE_HEADER = "| System | Split | N | Recall@5 | MRR | p50 (ms) | p95 (ms) |"
FREEZE_NOTE = (
    "> **Freeze note.** The labels and tolerance in `eval/queries.yaml` are frozen; the query-set and "
    "corpus hashes above pin those inputs, and the index line identifies the embedding model, revision, "
    "and size. A later ranking or pipeline change must not edit the labels — it appends a new dated "
    "table below."
)


@dataclass(frozen=True)
class Report:
    date: str
    command: str
    query_set_hash: str
    corpus_hash: str
    index: dict
    tables: dict[str, dict[str, Metrics]]
    title: str = "shotgrep eval results"


def render_markdown(report: Report) -> str:
    header = [
        f"# {report.title}",
        "",
        (
            f"Frozen query set: `eval/queries.yaml` (sha256 `{report.query_set_hash}`). "
            f"Corpus manifest: `corpus/manifest.json` (sha256 `{report.corpus_hash}`). "
            f"Index: {_index_text(report.index)}."
        ),
        f"Reproduce with `{report.command}`.",
        "",
        FREEZE_NOTE,
        "",
    ]
    return "\n".join(header) + "\n" + render_section(report)


def render_section(report: Report) -> str:
    """One dated table block; later runs append theirs below earlier ones."""
    lines = [f"## {report.date}", "", TABLE_HEADER, "|---|---|---|---|---|---|---|"]
    for system, by_split in report.tables.items():
        for split in _ordered(by_split):
            lines.append(_row(system, split, by_split[split]))
    return "\n".join(lines) + "\n"


def _ordered(by_split: dict[str, Metrics]) -> list[str]:
    preferred = ["overall", *SPLITS]
    ordered = [split for split in preferred if split in by_split]
    return ordered + sorted(split for split in by_split if split not in preferred)


def _row(system: str, split: str, metrics: Metrics) -> str:
    return (
        f"| {system} | {split} | {metrics.n} | {metrics.recall_at_5:.3f} | "
        f"{metrics.mrr:.3f} | {metrics.p50_ms:.0f} | {metrics.p95_ms:.0f} |"
    )


def _index_text(index: dict) -> str:
    return (
        f"{index['model']} {index['precision']} rev {index['revision']}; "
        f"{index['assets']} assets, {index['moments']} moments, index version {index['index_version']}"
    )
