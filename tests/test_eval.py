"""Eval harness unit tests: labels, metrics, query set, report rendering.

The benchmark itself is a quality gate run against a built index, not a CI
test (SPEC.md). These tests cover the pure seams the gate rests on so a change
to scoring or the frozen query set is caught without models or media.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.metrics import (
    Label,
    Metrics,
    Observation,
    is_relevant,
    percentile,
    recall_at_k,
    reciprocal_rank,
    score_by_film,
    score_by_split,
)
from eval.queries import SPLITS, QuerySetError, film_titles, index_asset_ids, load_queries
from eval.report import Report, render_markdown, render_section

REPO_ROOT = Path(__file__).resolve().parent.parent


def result(asset: str, start_s: float, end_s: float) -> dict:
    return {"asset_id": asset, "start_s": start_s, "end_s": end_s}


def test_is_relevant_matches_results_overlapping_the_label_within_tolerance() -> None:
    label = Label(asset="sintel", start_s=100.0, end_s=102.0)
    assert is_relevant(result("sintel", 101.0, 101.0), label)
    assert is_relevant(result("sintel", 97.0, 99.5), label)
    assert is_relevant(result("sintel", 103.5, 106.0), label)


def test_is_relevant_rejects_other_assets_and_gaps_beyond_tolerance() -> None:
    label = Label(asset="sintel", start_s=100.0, end_s=102.0)
    assert not is_relevant(result("big-buck-bunny", 101.0, 101.0), label)
    assert not is_relevant(result("sintel", 97.9, 97.9), label)
    assert not is_relevant(result("sintel", 104.1, 104.1), label)


def test_recall_at_k_is_the_share_of_queries_with_a_relevant_top_five_result() -> None:
    relevance = [
        [False, True],
        [False, False, False, False, False, True],
        [True],
    ]
    assert recall_at_k(relevance, 5) == pytest.approx(2 / 3)


def test_recall_at_k_of_an_empty_run_is_zero() -> None:
    with pytest.raises(ValueError, match="no queries"):
        recall_at_k([], 5)


def test_reciprocal_rank_scores_the_first_relevant_result() -> None:
    relevance = [
        [False, True, False],
        [False, False, True],
        [False, False, False],
    ]
    assert reciprocal_rank(relevance) == pytest.approx((1 / 2 + 1 / 3 + 0) / 3)


def test_percentile_interpolates_between_neighbours() -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0], 50) == pytest.approx(2.5)
    assert percentile([1.0, 2.0, 3.0, 4.0], 95) == pytest.approx(3.85)
    assert percentile([7.0], 95) == pytest.approx(7.0)
    with pytest.raises(ValueError, match="no latencies"):
        percentile([], 95)


def observation(split: str, relevant_at: int | None, latency_ms: float, asset: str = "sintel") -> Observation:
    label = Label(asset=asset, start_s=10.0, end_s=12.0)
    results = []
    for position in range(5):
        start = 11.0 if position == relevant_at else 500.0 + position
        results.append(result(asset, start, start))
    return Observation(split=split, label=label, results=results, latency_ms=latency_ms)


def test_score_by_split_reports_overall_and_per_split_metrics() -> None:
    metrics = score_by_split(
        [
            observation("easy", 0, 100.0),
            observation("easy", 2, 200.0),
            observation("negation", None, 300.0),
        ]
    )
    overall = metrics["overall"]
    assert overall.n == 3
    assert overall.recall_at_k == pytest.approx(2 / 3)
    assert overall.mrr == pytest.approx((1 + 1 / 3 + 0) / 3)
    assert overall.p50_ms == pytest.approx(200.0)
    assert overall.p95_ms == pytest.approx(290.0)
    easy = metrics["easy"]
    assert easy.n == 2
    assert easy.recall_at_k == 1.0
    assert easy.mrr == pytest.approx(2 / 3)
    negation = metrics["negation"]
    assert negation.n == 1
    assert negation.recall_at_k == 0.0
    assert negation.mrr == 0.0


def test_score_by_split_scores_recall_at_the_requested_k() -> None:
    metrics = score_by_split(
        [
            observation("easy", 0, 100.0),
            observation("easy", 2, 200.0),
            observation("easy", 4, 300.0),
        ],
        k=2,
    )
    assert metrics["overall"].recall_at_k == pytest.approx(1 / 3)
    assert metrics["easy"].recall_at_k == pytest.approx(1 / 3)


def test_score_by_split_scores_mrr_within_the_requested_k() -> None:
    label = Label(asset="sintel", start_s=10.0, end_s=12.0)
    results = [result("sintel", 500.0 + position, 500.0 + position) for position in range(5)]
    results.append(result("sintel", 11.0, 11.0))
    observation = Observation(split="easy", label=label, results=results, latency_ms=100.0)
    assert score_by_split([observation], k=5)["overall"].mrr == 0.0
    assert score_by_split([observation], k=6)["overall"].mrr == pytest.approx(1 / 6)


def test_score_by_film_groups_metrics_by_label_asset() -> None:
    metrics = score_by_film(
        [
            observation("easy", 0, 100.0, asset="sintel-hash"),
            observation("easy", None, 200.0, asset="sintel-hash"),
            observation("negation", 1, 300.0, asset="tos-hash"),
        ]
    )
    assert set(metrics) == {"sintel-hash", "tos-hash"}
    sintel = metrics["sintel-hash"]
    assert sintel.n == 2
    assert sintel.recall_at_k == 0.5
    assert sintel.mrr == pytest.approx(0.5)
    tears = metrics["tos-hash"]
    assert tears.n == 1
    assert tears.recall_at_k == 1.0
    assert tears.mrr == pytest.approx(0.5)


def test_score_by_film_names_assets_for_reporting() -> None:
    metrics = score_by_film(
        [observation("easy", 0, 100.0, asset="sintel-hash")],
        names={"sintel-hash": "Sintel"},
    )
    assert set(metrics) == {"Sintel"}


def test_score_by_film_of_an_empty_run_is_zero() -> None:
    with pytest.raises(ValueError, match="no queries"):
        score_by_film([])


QUERY_SET = """
version: 1
frozen_on: "2026-09-20"
tolerance_s: 2.0
queries:
  - id: easy-01
    split: easy
    text: a robot hand on a table
    asset: tears-of-steel
    start_s: 100.0
    end_s: 102.0
  - id: negation-01
    split: negation
    text: a forest with no animals
    asset: sintel
    start_s: 50.0
    end_s: 51.0
"""


def write_query_set(tmp_path, body: str):
    path = tmp_path / "queries.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_queries_reads_the_frozen_set(tmp_path) -> None:
    query_set = load_queries(write_query_set(tmp_path, QUERY_SET))
    assert query_set.version == 1
    assert query_set.frozen_on == "2026-09-20"
    assert query_set.tolerance_s == 2.0
    assert [query.id for query in query_set.queries] == ["easy-01", "negation-01"]
    assert query_set.queries[0].split == "easy"
    assert query_set.queries[0].label == Label(asset="tears-of-steel", start_s=100.0, end_s=102.0)
    assert query_set.queries[1].text == "a forest with no animals"


def test_load_queries_rejects_an_unknown_split(tmp_path) -> None:
    body = QUERY_SET.replace("split: negation", "split: vibes")
    with pytest.raises(QuerySetError, match="vibes"):
        load_queries(write_query_set(tmp_path, body))


def test_load_queries_rejects_duplicate_ids(tmp_path) -> None:
    body = QUERY_SET.replace("id: negation-01", "id: easy-01")
    with pytest.raises(QuerySetError, match="duplicate"):
        load_queries(write_query_set(tmp_path, body))


def test_load_queries_rejects_inverted_ranges(tmp_path) -> None:
    body = QUERY_SET.replace("start_s: 50.0", "start_s: 60.0")
    with pytest.raises(QuerySetError, match="start_s"):
        load_queries(write_query_set(tmp_path, body))


def test_load_queries_rejects_a_missing_field(tmp_path) -> None:
    body = QUERY_SET.replace("    asset: sintel\n", "")
    with pytest.raises(QuerySetError, match="asset"):
        load_queries(write_query_set(tmp_path, body))


def test_index_asset_ids_maps_corpus_slugs_to_content_hashes(tmp_path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"assets": [{"id": "sintel", "sha256": "abc"}, {"id": "tears-of-steel", "sha256": "def"}]}),
        encoding="utf-8",
    )
    assert index_asset_ids(path) == {"sintel": "abc", "tears-of-steel": "def"}


def test_film_titles_map_content_hashes_to_readable_film_names(tmp_path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "assets": [
                    {"id": "sintel", "sha256": "abc", "title": "Sintel"},
                    {"id": "tears-of-steel", "sha256": "def", "title": "Tears of Steel"},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert film_titles(path) == {"abc": "Sintel", "def": "Tears of Steel"}


def test_observe_runs_every_query_once_in_frozen_order(tmp_path) -> None:
    from eval.harness import observe

    class FakeSystem:
        name = "fake"

        def __init__(self) -> None:
            self.calls: list[tuple[str, int]] = []

        def search(self, query: str, *, k: int) -> list[dict]:
            self.calls.append((query, k))
            return [result("tos-hash", 101.0, 101.0)]

    system = FakeSystem()
    query_set = load_queries(write_query_set(tmp_path, QUERY_SET))
    observations = observe(system, query_set, asset_ids={"tears-of-steel": "tos-hash", "sintel": "sintel-hash"})
    assert system.calls == [
        ("warm up", 1),
        ("a robot hand on a table", 10),
        ("a forest with no animals", 10),
    ]
    assert [observation.split for observation in observations] == ["easy", "negation"]
    assert all(observation.latency_ms >= 0.0 for observation in observations)
    assert score_by_split(observations)["overall"].recall_at_k == 0.5


def test_observe_measures_at_the_requested_k(tmp_path) -> None:
    from eval.harness import observe

    class FakeSystem:
        name = "fake"

        def __init__(self) -> None:
            self.calls: list[tuple[str, int]] = []

        def search(self, query: str, *, k: int) -> list[dict]:
            self.calls.append((query, k))
            return [result("tos-hash", 101.0, 101.0)]

    system = FakeSystem()
    query_set = load_queries(write_query_set(tmp_path, QUERY_SET))
    observe(system, query_set, asset_ids={"tears-of-steel": "tos-hash", "sintel": "sintel-hash"}, k=3)
    assert [k for _, k in system.calls] == [1, 3, 3]


def test_build_parser_defaults_to_the_service_k_and_accepts_an_override() -> None:
    from api.service import DEFAULT_K
    from eval.harness import build_parser

    parser = build_parser()
    assert parser.parse_args([]).k == DEFAULT_K
    assert parser.parse_args(["--k", "3"]).k == 3


def report(*, recall_k: int = 5, run_k: int = 10) -> Report:
    return Report(
        date="2026-09-20",
        command="uv run python -m eval --index work/index --k 10",
        query_set_hash="a" * 64,
        corpus_hash="b" * 64,
        index={
            "model": "Xenova/siglip-base-patch16-224",
            "precision": "int8",
            "revision": "4649052",
            "assets": 4,
            "moments": 3000,
            "index_version": 3,
        },
        tables={
            "shipped fused": {
                "overall": Metrics(n=60, recall_at_k=0.72, mrr=0.5432, p50_ms=120.4, p95_ms=210.9),
                "easy": Metrics(n=15, recall_at_k=0.9333, mrr=0.8, p50_ms=110.0, p95_ms=180.0),
            },
            "baseline visual": {
                "overall": Metrics(n=60, recall_at_k=0.5, mrr=0.3333, p50_ms=90.0, p95_ms=150.0),
            },
        },
        films={
            "shipped fused": {
                "Sintel": Metrics(n=16, recall_at_k=0.6875, mrr=0.5, p50_ms=115.0, p95_ms=190.0),
                "Tears of Steel": Metrics(n=16, recall_at_k=0.375, mrr=0.3, p50_ms=130.0, p95_ms=220.0),
            },
            "baseline visual": {
                "Sintel": Metrics(n=16, recall_at_k=0.5, mrr=0.4, p50_ms=80.0, p95_ms=140.0),
            },
        },
        run_k=run_k,
        recall_k=recall_k,
    )


def test_render_markdown_commits_the_run_as_a_dated_table() -> None:
    text = render_markdown(report())
    assert "Freeze note" in text
    assert "[eval/ANALYSIS.md](ANALYSIS.md)" in text
    assert "## 2026-09-20" in text
    assert "| System | Split | N | Recall@5 | MRR | p50 (ms) | p95 (ms) |" in text
    assert "| shipped fused | overall | 60 | 0.720 | 0.543 | 120 | 211 |" in text
    assert "| shipped fused | easy | 15 | 0.933 | 0.800 | 110 | 180 |" in text
    assert "| baseline visual | overall | 60 | 0.500 | 0.333 | 90 | 150 |" in text


def test_render_section_carries_the_inputs_and_index_of_its_own_run() -> None:
    text = render_section(report())
    assert text.startswith("## 2026-09-20")
    assert "a" * 64 in text
    assert "b" * 64 in text
    assert "index version 3" in text
    assert "Latency measured at k=10; Recall@5 scored from the top 5 of the same run." in text
    assert "Reproduce with `uv run python -m eval --index work/index --k 10`." in text
    assert "Freeze note" not in text


def test_render_section_reports_per_film_rows() -> None:
    text = render_section(report())
    assert "**By film**" in text
    assert "| System | Film | N | Recall@5 | MRR | p50 (ms) | p95 (ms) |" in text
    assert "| shipped fused | Sintel | 16 | 0.688 | 0.500 | 115 | 190 |" in text
    assert "| shipped fused | Tears of Steel | 16 | 0.375 | 0.300 | 130 | 220 |" in text
    assert "| baseline visual | Sintel | 16 | 0.500 | 0.400 | 80 | 140 |" in text


def test_render_section_generalises_the_recall_header_to_the_scored_k() -> None:
    text = render_section(report(recall_k=3, run_k=3))
    assert "| System | Split | N | Recall@3 | MRR | p50 (ms) | p95 (ms) |" in text
    assert "Latency measured at k=3; Recall@3 scored from the top 3 of the same run." in text
    assert "Recall@5" not in text


def test_check_coverage_rejects_an_index_missing_a_corpus_asset(tmp_path) -> None:
    import lancedb

    from eval.harness import check_coverage
    from pipeline.errors import IngestError

    db = lancedb.connect(str(tmp_path / "index"))
    db.create_table("assets", [{"id": "sintel-hash"}])
    with pytest.raises(IngestError, match="tears-of-steel"):
        check_coverage(tmp_path / "index", {"tears-of-steel": "tos-hash", "sintel": "sintel-hash"})


def test_check_coverage_needs_a_built_index(tmp_path) -> None:
    from eval.harness import check_coverage
    from pipeline.errors import IngestError

    with pytest.raises(IngestError, match="no index"):
        check_coverage(tmp_path / "missing", {"sintel": "sintel-hash"})


def test_check_coverage_accepts_an_index_holding_every_corpus_asset(tmp_path) -> None:
    import lancedb

    from eval.harness import check_coverage

    db = lancedb.connect(str(tmp_path / "index"))
    db.create_table("assets", [{"id": "sintel-hash"}, {"id": "tos-hash"}])
    check_coverage(tmp_path / "index", {"tears-of-steel": "tos-hash", "sintel": "sintel-hash"})


def test_frozen_query_set_covers_every_split_within_the_corpus() -> None:
    query_set = load_queries(REPO_ROOT / "eval" / "queries.yaml")
    assert query_set.version == 1
    assert query_set.frozen_on
    assert query_set.tolerance_s == 2.0
    assert 50 <= len(query_set.queries) <= 70
    for split in SPLITS:
        assert len(query_set.of_split(split)) >= 12, split
    durations = {
        asset["id"]: asset["duration_s"]
        for asset in json.loads((REPO_ROOT / "corpus" / "manifest.json").read_text(encoding="utf-8"))["assets"]
    }
    assert {query.asset for query in query_set.queries} == set(durations)
    for query in query_set.queries:
        assert query.asset in durations, query.id
        assert 0.0 <= query.start_s <= query.end_s < durations[query.asset], query.id
