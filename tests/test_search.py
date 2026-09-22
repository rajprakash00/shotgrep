"""Read contract: the CLI query returns moments with correct timestamps.

One full ingest is shared by the module; every test drives `shotgrep search`
as a subprocess and asserts external behavior only. ffprobe (FFmpeg) must be
on PATH and the SigLIP int8 assets are fetched on first use.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import lancedb
import pyarrow as pa
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "clip.mp4"
TEST_ENV = {
    "SHOTGREP_ASR_MODEL": "tiny",
    "SHOTGREP_ASR_DEVICE": "cpu",
    "SHOTGREP_EMBED_MODEL": "Xenova/siglip-base-patch16-224",
    "SHOTGREP_EMBED_PRECISION": "int8",
}
ENV = {**os.environ, **TEST_ENV}


def run_cli(command: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pipeline", command, *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=ENV,
    )


@pytest.fixture(scope="module")
def ingested(tmp_path_factory: pytest.TempPathFactory) -> Path:
    work = tmp_path_factory.mktemp("search") / "work"
    result = run_cli("ingest", str(FIXTURE), "--work-dir", str(work))
    assert result.returncode == 0, result.stderr
    return work


def search_payload(work_dir: Path, query: str, *args: str) -> dict:
    result = run_cli("search", query, "--work-dir", str(work_dir), *args)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def manifest(work_dir: Path) -> dict:
    found = sorted(Path(work_dir).glob("*/manifest.json"))
    assert len(found) == 1
    return json.loads(found[0].read_text(encoding="utf-8"))


def test_query_returns_known_moment_with_correct_timestamp(ingested: Path) -> None:
    # The fixture opens on a 2-second city shot, then a bridge scene.
    payload = search_payload(ingested, "a futuristic city skyline", "-k", "5")
    results = payload["results"]
    assert results, "expected at least one result"
    top = results[0]
    assert 0.0 <= top["start_s"] <= 1.0, f"city moment expected near 0s, got {top}"
    assert top["kind"] in {"frame", "shot_start", "transcript"}

    payload = search_payload(ingested, "two people standing on a bridge", "-k", "5")
    bridge = [
        result
        for result in payload["results"]
        if result["kind"] == "shot_start" and result["start_s"] == 2.0
    ]
    assert bridge, f"bridge shot start expected in the top 5, got {payload['results']}"


def test_query_uses_the_index_embedding_model(ingested: Path) -> None:
    payload = search_payload(ingested, "a bridge", "-k", "1")
    outputs = manifest(ingested)["stages"]["embed"]["outputs"]
    assert payload["model"] == {
        "name": outputs["model"],
        "precision": outputs["precision"],
        "revision": outputs["revision"],
    }


def test_results_carry_the_read_contract(ingested: Path) -> None:
    payload = search_payload(ingested, "a bridge", "-k", "3")
    results = payload["results"]
    assert len(results) == 3
    scores = [result["score"] for result in results]
    assert scores == sorted(scores, reverse=True)
    for result in results:
        assert set(result) == {
            "moment_id",
            "asset_id",
            "kind",
            "start_s",
            "end_s",
            "thumbnail_url",
            "snippet",
            "score",
            "deep_link",
        }
        assert result["end_s"] >= result["start_s"]
        assert result["thumbnail_url"].endswith(f"{round(result['start_s'] * 1000):08d}.jpg")
        served = result["thumbnail_url"].removeprefix("http://localhost:8000/media/")
        assert (ingested / "index" / served).is_file()
        assert result["deep_link"] == (
            f"http://localhost:3000/watch/{result['asset_id']}?t={result['start_s']:g}"
        )


def test_search_matches_a_spoken_line_by_meaning(ingested: Path) -> None:
    # The words share nothing with the transcript, so the lexical gate stays
    # shut; only the dense transcript channel can surface the robotics line.
    payload = search_payload(ingested, "science and technology excite him and he dreams of the stars", "-k", "5")
    transcripts = [result for result in payload["results"] if result["kind"] == "transcript"]
    assert transcripts, f"expected a dense transcript hit, got {payload['results']}"
    assert any("robotics" in (result["snippet"] or "") for result in transcripts), transcripts


def test_search_refuses_an_index_from_another_model(ingested: Path, tmp_path: Path) -> None:
    work = tmp_path / "work"
    shutil.copytree(ingested, work)
    db = lancedb.connect(str(work / "index"))
    table = db.open_table("moments")
    arrow = table.to_arrow()
    rows = arrow.to_pylist()
    for row in rows:
        row["embedding_model"] = "other/model"
    db.create_table(
        "moments",
        data=pa.Table.from_pylist(rows, schema=arrow.schema),
        mode="overwrite",
        on_bad_vectors="null",
    )

    result = run_cli("search", "anything", "--work-dir", str(work))
    assert result.returncode != 0
    assert "another model" in result.stderr
    assert result.stdout == ""


def test_search_refuses_an_index_from_another_text_model(ingested: Path, tmp_path: Path) -> None:
    work = tmp_path / "work"
    shutil.copytree(ingested, work)
    db = lancedb.connect(str(work / "index"))
    table = db.open_table("moments")
    arrow = table.to_arrow()
    rows = arrow.to_pylist()
    for row in rows:
        if row["kind"] == "transcript":
            row["text_embedding_model"] = "other/text-model"
    db.create_table(
        "moments",
        data=pa.Table.from_pylist(rows, schema=arrow.schema),
        mode="overwrite",
        on_bad_vectors="null",
    )

    result = run_cli("search", "anything", "--work-dir", str(work))
    assert result.returncode != 0
    assert "another text model" in result.stderr
    assert result.stdout == ""


def test_query_without_an_index_fails_cleanly(tmp_path: Path) -> None:
    result = run_cli("search", "anything", "--work-dir", str(tmp_path / "work"))
    assert result.returncode != 0
    assert "index" in result.stderr.lower()
    assert result.stdout == ""
