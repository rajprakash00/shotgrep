"""Render an eval run as the markdown tables committed to eval/RESULTS.md.

One dated section per run; the section carries its own inputs, index, and k, so
appending a later run cannot relabel an earlier one. The freeze note pins the
rule plainly: later ranking changes append a new dated table instead of editing
the labels. The renderer is pure so the committed table can be regenerated
deterministically from a Report.
"""

from __future__ import annotations

from dataclasses import dataclass

from eval.metrics import Metrics
from eval.queries import SPLITS

FREEZE_NOTE = (
    "> **Freeze note.** The labels and tolerance in `eval/queries.yaml` are frozen; each run's section "
    "pins the query-set and corpus hashes it scored, and its index line identifies the embedding model, "
    "revision, and size. A later ranking or pipeline change must not edit the labels — it appends a new "
    "dated table below."
)


@dataclass(frozen=True)
class Report:
    date: str
    command: str
    query_set_hash: str
    corpus_hash: str
    index: dict
    tables: dict[str, dict[str, Metrics]]
    films: dict[str, dict[str, Metrics]]
    run_k: int
    recall_k: int
    title: str = "shotgrep eval results"


def render_markdown(report: Report) -> str:
    header = [
        f"# {report.title}",
        "",
        "Analysis and next actions: [eval/ANALYSIS.md](ANALYSIS.md).",
        "",
        FREEZE_NOTE,
        "",
    ]
    return "\n".join(header) + "\n" + render_section(report)


def render_section(report: Report) -> str:
    """One dated run; later runs append theirs below earlier ones."""
    lines = [
        f"## {report.date}",
        "",
        (
            f"Frozen query set: `eval/queries.yaml` (sha256 `{report.query_set_hash}`). "
            f"Corpus manifest: `corpus/manifest.json` (sha256 `{report.corpus_hash}`). "
            f"Index: {_index_text(report.index)}."
        ),
        (
            f"Latency measured at k={report.run_k}; Recall@{report.recall_k} scored from the top "
            f"{report.recall_k} of the same run."
        ),
        f"Reproduce with `{report.command}`.",
        "",
        "**By split**",
        "",
        _table(report.tables, "Split", report.recall_k),
        "",
        "**By film**",
        "",
        _table(report.films, "Film", report.recall_k),
    ]
    return "\n".join(lines) + "\n"


def _table(tables: dict[str, dict[str, Metrics]], column: str, recall_k: int) -> str:
    lines = [_header(column, recall_k), "|---|---|---|---|---|---|---|"]
    for system, by_group in tables.items():
        for group in _ordered(by_group):
            lines.append(_row(system, group, by_group[group]))
    return "\n".join(lines)


def _header(column: str, recall_k: int) -> str:
    return f"| System | {column} | N | Recall@{recall_k} | MRR | p50 (ms) | p95 (ms) |"


def _ordered(by_group: dict[str, Metrics]) -> list[str]:
    preferred = ["overall", *SPLITS]
    ordered = [group for group in preferred if group in by_group]
    return ordered + sorted(group for group in by_group if group not in preferred)


def _row(system: str, group: str, metrics: Metrics) -> str:
    return (
        f"| {system} | {group} | {metrics.n} | {metrics.recall_at_k:.3f} | "
        f"{metrics.mrr:.3f} | {metrics.p50_ms:.0f} | {metrics.p95_ms:.0f} |"
    )


def _index_text(index: dict) -> str:
    return (
        f"{index['model']} {index['precision']} rev {index['revision']}; "
        f"{index['assets']} assets, {index['moments']} moments, index version {index['index_version']}"
    )
