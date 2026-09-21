"""Run the frozen query set through the shipped search and a visual baseline.

One command reproduces the results table from a built index:

    uv run python -m eval --index work/index

A later ranking change reruns the same command and appends its dated section
(`--out eval/RESULTS.md --append`), so earlier tables stay put.

The shipped system is QueryService — the same service behind REST — so the
numbers describe what users get. The baseline is single-stage visual retrieval:
the same index, the same query embeddings, but ANN over visual moments only,
with no transcript channel, no score normalization, no shot-start prior, and
no near-duplicate collapse. Both run on the same corpus and sampling, so the
difference is attributable to retrieval and fusion. Latency is measured after
a warm-up so model load does not pollute p50/p95. This is a quality gate, not
a CI test (SPEC.md); the output is committed to eval/RESULTS.md.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from datetime import date
from pathlib import Path
from typing import Protocol

import lancedb

from api.retrieval import VISUAL_KIND_CLAUSE, Hit, visual_hits
from api.service import QueryService
from eval.metrics import RECALL_K, Label, Observation, score_by_split
from eval.queries import QuerySet, QuerySetError, index_asset_ids, load_queries
from eval.report import Report, render_markdown, render_section
from pipeline.errors import IngestError
from pipeline.models.embedder import SiglipOnnxEmbedder
from pipeline.stages.index import ASSETS, MOMENTS

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = REPO_ROOT / "work" / "index"
DEFAULT_QUERIES = REPO_ROOT / "eval" / "queries.yaml"
DEFAULT_CORPUS = REPO_ROOT / "corpus" / "manifest.json"
WARMUP_QUERY = "warm up"


class System(Protocol):
    """One ranking system under measurement."""

    name: str

    def search(self, query: str, *, k: int) -> list[dict]: ...


class ShippedFused:
    """The shipped fused search: QueryService, exactly as REST calls it."""

    name = "shipped fused"

    def __init__(self, service: QueryService) -> None:
        self.service = service

    def search(self, query: str, *, k: int) -> list[dict]:
        return self.service.search(query, k=k)["results"]


class BaselineVisual:
    """Single-stage visual retrieval: ANN over visual moments, nothing else."""

    name = "baseline visual"

    def __init__(self, index_dir: Path, embedder: SiglipOnnxEmbedder) -> None:
        self.embedder = embedder
        self.table = lancedb.connect(str(index_dir)).open_table(MOMENTS)

    def search(self, query: str, *, k: int) -> list[dict]:
        vector = self.embedder.embed_text(query).tolist()
        return [_result(hit) for hit in visual_hits(self.table, vector, VISUAL_KIND_CLAUSE, k)]


def build_systems(index_dir: Path) -> list[System]:
    """Both systems share one embedder, so query vectors are identical."""
    embedder = SiglipOnnxEmbedder()
    service = QueryService(index_dir, embedder=embedder)
    return [ShippedFused(service), BaselineVisual(index_dir, embedder)]


def observe(
    system: System,
    query_set: QuerySet,
    asset_ids: dict[str, str],
    *,
    k: int = RECALL_K,
) -> list[Observation]:
    system.search(WARMUP_QUERY, k=1)
    observations = []
    for query in query_set.queries:
        if query.asset not in asset_ids:
            raise QuerySetError(f"query {query.id} names asset {query.asset!r}, which is not in the corpus manifest")
        started = time.perf_counter()
        results = system.search(query.text, k=k)
        latency_ms = (time.perf_counter() - started) * 1000
        label = Label(asset=asset_ids[query.asset], start_s=query.start_s, end_s=query.end_s)
        observations.append(Observation(split=query.split, label=label, results=results, latency_ms=latency_ms))
    return observations


def measure(index_dir: Path, query_set: QuerySet, asset_ids: dict[str, str]) -> dict[str, list[Observation]]:
    check_coverage(index_dir, asset_ids)
    return {system.name: observe(system, query_set, asset_ids) for system in build_systems(index_dir)}


def indexed_asset_ids(index_dir: Path) -> set[str]:
    """Asset ids present in a built index (media content hashes)."""
    if not index_dir.is_dir():
        raise IngestError(f"no index at {index_dir}; run `shotgrep ingest` first")
    db = lancedb.connect(str(index_dir))
    if ASSETS not in set(db.list_tables().tables):
        raise IngestError(f"the index at {index_dir} has no {ASSETS} table; re-ingest")
    rows = db.open_table(ASSETS).search().limit(10_000).to_list()
    return {row["id"] for row in rows}


def check_coverage(index_dir: Path, asset_ids: dict[str, str]) -> None:
    """Refuse to score a query set against an index that is missing its assets.

    Without this, a partially built index scores those queries zero and the
    table describes a different corpus than the frozen labels do.
    """
    indexed = indexed_asset_ids(index_dir)
    missing = sorted(slug for slug, asset_id in asset_ids.items() if asset_id not in indexed)
    if missing:
        raise IngestError(f"the index at {index_dir} holds no moments for {', '.join(missing)}; re-ingest")


def index_metadata(index_dir: Path) -> dict:
    db = lancedb.connect(str(index_dir))
    moments = db.open_table(MOMENTS)
    sample = moments.search().limit(1).to_list()
    if not sample:
        raise IngestError(f"the index at {index_dir} has no moments; re-ingest")
    row = sample[0]
    return {
        "model": row["embedding_model"],
        "precision": row["embedding_precision"],
        "revision": row["embedding_revision"],
        "assets": db.open_table(ASSETS).count_rows(),
        "moments": moments.count_rows(),
        "index_version": row["index_version"],
    }


def file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_report(
    *,
    index_dir: Path,
    query_set: QuerySet,
    observations: dict[str, list[Observation]],
    queries_path: Path,
    corpus_path: Path,
    run_date: str,
    command: str,
) -> Report:
    return Report(
        date=run_date,
        command=command,
        query_set_hash=file_hash(queries_path),
        corpus_hash=file_hash(corpus_path),
        index=index_metadata(index_dir),
        tables={
            system: score_by_split(rows, k=RECALL_K, tolerance_s=query_set.tolerance_s)
            for system, rows in observations.items()
        },
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m eval",
        description="Measure Recall@5, MRR, and latency over the frozen query set on a built index.",
    )
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX, help="built index directory")
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES, help="frozen query set")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS, help="corpus manifest")
    parser.add_argument("--date", default=None, help="run date for the table (default: today)")
    parser.add_argument("--out", type=Path, default=None, help="also write the markdown table here")
    parser.add_argument(
        "--append",
        action="store_true",
        help="append this run's dated section to --out instead of replacing it",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.append and args.out is None:
        parser.error("--append needs --out")
    try:
        query_set = load_queries(args.queries)
        observations = measure(args.index, query_set, index_asset_ids(args.corpus))
        report = build_report(
            index_dir=args.index,
            query_set=query_set,
            observations=observations,
            queries_path=args.queries,
            corpus_path=args.corpus,
            run_date=args.date or date.today().isoformat(),
            command=" ".join(
                [
                    "uv run python -m eval",
                    f"--index {_display(args.index)}",
                    f"--queries {_display(args.queries)}",
                    f"--corpus {_display(args.corpus)}",
                ]
            ),
        )
    except (QuerySetError, IngestError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    section = render_section(report)
    if args.out is not None and args.append and args.out.exists():
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("a", encoding="utf-8") as handle:
            handle.write("\n" + section)
        print(section, end="")
        return 0
    table = render_markdown(report)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(table, encoding="utf-8")
    print(table, end="")
    return 0


def _result(hit: Hit) -> dict:
    return {
        "moment_id": hit.moment_id,
        "asset_id": hit.asset_id,
        "kind": hit.kind,
        "start_s": hit.start_s,
        "end_s": hit.end_s,
    }


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
