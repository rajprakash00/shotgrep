"""Read contract: REST is a thin layer over one query service.

One ingest of the fixture clip plus a generated second clip is shared by the
module; every test drives the FastAPI app through TestClient and asserts
external behavior only (payload shape, filtering, fusion, lookups). The CLI
comparison test shows both public surfaces present the same contract.
ffprobe (FFmpeg) must be on PATH; SigLIP int8 assets are fetched on first use.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from api.app import create_app

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "clip.mp4"
FIXTURE_SHA256 = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
API_URL = "https://api.test"
WEB_URL = "https://web.test"
RESULT_KEYS = {
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
TEST_ENV = {
    "SHOTGREP_ASR_MODEL": "tiny",
    "SHOTGREP_ASR_DEVICE": "cpu",
    "SHOTGREP_EMBED_MODEL": "Xenova/siglip-base-patch16-224",
    "SHOTGREP_EMBED_PRECISION": "int8",
}
# The CLI reads the same URL configuration as the app fixture below.
URL_ENV = {"SHOTGREP_API_URL": API_URL, "SHOTGREP_WEB_URL": WEB_URL}
ENV = {**os.environ, **TEST_ENV}


def run_cli(command: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pipeline", command, *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**ENV, **(env or {})},
    )


def write_second_clip(path: Path) -> None:
    completed = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:d=3:r=24",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.fixture(scope="module")
def second_clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("clip") / "blue.mp4"
    write_second_clip(path)
    return path


@pytest.fixture(scope="module")
def work_dir(tmp_path_factory: pytest.TempPathFactory, second_clip: Path) -> Path:
    work = tmp_path_factory.mktemp("api") / "work"
    first = run_cli("ingest", str(FIXTURE), "--work-dir", str(work))
    assert first.returncode == 0, first.stderr
    second = run_cli("ingest", str(second_clip), "--work-dir", str(work))
    assert second.returncode == 0, second.stderr
    return work


@pytest.fixture(scope="module")
def client(work_dir: Path) -> TestClient:
    return TestClient(create_app(work_dir, api_url=API_URL, web_url=WEB_URL))


def search(client: TestClient, query: str, **params: object) -> dict:
    response = client.get("/search", params={"q": query, **params})
    assert response.status_code == 200, response.text
    return response.json()


def thumbnail_file(work_dir: Path, url: str) -> Path:
    assert url.startswith(f"{API_URL}/media/"), url
    return work_dir / "index" / url.removeprefix(f"{API_URL}/media/")


def test_search_returns_the_full_result_contract(client: TestClient) -> None:
    payload = search(client, "robotics", k=3)
    assert payload["query"] == "robotics"
    assert payload["model"]["name"] == "Xenova/siglip-base-patch16-224"
    assert payload["model"]["precision"] == "int8"
    assert payload["model"]["revision"]
    results = payload["results"]
    assert len(results) == 3
    scores = [result["score"] for result in results]
    assert scores == sorted(scores, reverse=True)
    for result in results:
        assert set(result) == RESULT_KEYS
        assert 0.0 <= result["score"] <= 1.0
        assert result["end_s"] >= result["start_s"]
        assert result["deep_link"].startswith(f"{WEB_URL}/watch/{result['asset_id']}?t=")


def test_search_result_sources_are_fused(client: TestClient) -> None:
    kinds = {result["kind"] for result in search(client, "robotics space", k=5)["results"]}
    assert "transcript" in kinds, f"keyword retrieval missing from {kinds}"
    assert kinds & {"frame", "shot_start"}, f"visual retrieval missing from {kinds}"


def test_search_collapses_near_duplicate_moments(client: TestClient) -> None:
    results = search(client, "two people standing on a bridge", k=6)["results"]
    kept: list[dict] = []
    for result in results:
        duplicate = any(
            other["asset_id"] == result["asset_id"]
            and other["kind"] == result["kind"]
            and abs(other["start_s"] - result["start_s"]) < 1.5
            for other in kept
        )
        assert not duplicate, f"near-duplicate survived collapse: {result}"
        kept.append(result)


def test_search_filters_by_asset(client: TestClient, second_clip: Path) -> None:
    blue = hashlib.sha256(second_clip.read_bytes()).hexdigest()
    assert blue != FIXTURE_SHA256
    payload = search(client, "anything blue", asset=blue, k=5)
    assert payload["results"], "expected the blue clip to match its own asset filter"
    assert {result["asset_id"] for result in payload["results"]} == {blue}


def test_search_filters_by_time_range(client: TestClient) -> None:
    unfiltered = search(client, "robotics", asset=FIXTURE_SHA256, k=5)["results"]
    assert any(
        result["kind"] == "transcript" and result["start_s"] == 4.44 for result in unfiltered
    ), unfiltered

    payload = search(client, "robotics", asset=FIXTURE_SHA256, start_s=2.0, end_s=4.0, k=5)
    results = payload["results"]
    assert results
    for result in results:
        assert result["end_s"] >= 2.0 and result["start_s"] <= 4.0, result
    assert all(result["kind"] != "transcript" for result in results), "4.44s transcript is outside the range"


def test_search_ranking_is_independent_of_k(client: TestClient) -> None:
    few = search(client, "robotics", k=3)["results"]
    many = search(client, "robotics", k=10)["results"]
    assert [result["moment_id"] for result in few] == [result["moment_id"] for result in many[:3]]


def test_search_priors_shot_starts_above_mid_shot_samples(client: TestClient) -> None:
    # The bridge shot's mid-shot frames outscore its first frame on raw visual
    # similarity; the shot-start prior puts the shot start on top.
    top = search(client, "two people standing on a bridge", k=1)["results"][0]
    assert top["kind"] == "shot_start"
    assert top["start_s"] == 2.0


def test_search_matches_the_cli_read_contract(client: TestClient, work_dir: Path) -> None:
    completed = run_cli("search", "robotics", "--work-dir", str(work_dir), "-k", "3", env=URL_ENV)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == search(client, "robotics", k=3)


def test_thumbnails_are_served_at_the_result_url(client: TestClient, work_dir: Path) -> None:
    result = search(client, "a bridge", k=1)["results"][0]
    assert thumbnail_file(work_dir, result["thumbnail_url"]).is_file()
    response = client.get(urlparse(result["thumbnail_url"]).path)
    assert response.status_code == 200
    assert response.content[:2] == b"\xff\xd8"


def test_moment_lookup_returns_the_indexed_moment(client: TestClient, work_dir: Path) -> None:
    moment_id = f"{FIXTURE_SHA256}-transcript-00004440"
    response = client.get(f"/moments/{moment_id}")
    assert response.status_code == 200, response.text
    moment = response.json()
    assert set(moment) == RESULT_KEYS
    assert moment["moment_id"] == moment_id
    assert moment["asset_id"] == FIXTURE_SHA256
    assert moment["kind"] == "transcript"
    assert moment["start_s"] == 4.44
    assert moment["end_s"] > moment["start_s"]
    assert "robotics" in moment["snippet"]
    assert moment["score"] is None
    assert moment["deep_link"] == f"{WEB_URL}/watch/{FIXTURE_SHA256}?t=4.44"
    assert thumbnail_file(work_dir, moment["thumbnail_url"]).is_file()


def test_moment_lookup_unknown_id_is_404(client: TestClient) -> None:
    response = client.get("/moments/not-a-moment")
    assert response.status_code == 404
    assert "not-a-moment" in response.json()["detail"]


def test_transcript_range_returns_segments_with_words(client: TestClient) -> None:
    response = client.get(
        f"/assets/{FIXTURE_SHA256}/transcript", params={"start_s": 1.5, "end_s": 4.5}
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["asset_id"] == FIXTURE_SHA256
    assert payload["start_s"] == 1.5
    assert payload["end_s"] == 4.5
    texts = [segment["text"] for segment in payload["segments"]]
    assert texts == [
        "Look, Celia, we have to follow our passions.",
        "You have your robotics, and I just want to be awesome in space.",
    ]
    for segment in payload["segments"]:
        assert segment["end_s"] > segment["start_s"]
        words = segment["words"]
        assert words, segment
        assert [word["start_s"] for word in words] == sorted(word["start_s"] for word in words)
        for word in words:
            assert set(word) == {"word", "start_s", "end_s"}
            assert word["start_s"] >= segment["start_s"] - 0.01
            assert word["end_s"] <= segment["end_s"] + 0.01


def test_transcript_range_defaults_to_the_whole_asset(client: TestClient) -> None:
    payload = client.get(f"/assets/{FIXTURE_SHA256}/transcript").json()
    assert payload["start_s"] == 0.0
    assert payload["end_s"] == 10.0
    assert len(payload["segments"]) == 4


def test_transcript_range_unknown_asset_is_404(client: TestClient) -> None:
    response = client.get("/assets/nope/transcript")
    assert response.status_code == 404
    assert "nope" in response.json()["detail"]


def test_search_against_a_missing_index_fails_cleanly(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "work", api_url=API_URL, web_url=WEB_URL))
    response = client.get("/search", params={"q": "anything"})
    assert response.status_code == 503
    assert "index" in response.json()["detail"].lower()
