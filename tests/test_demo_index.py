"""Ship contract: the committed demo index serves the corpus on its own.

The demo deploys `index/` (search tables, transcripts, thumbnails) with no
`work/` artifacts and no corpus media. This is an artifact test, not a stage
test: the index is the deployed deliverable, so its contents are asserted
directly, and the same app the deployment runs is driven over it. SigLIP and
bge int8 assets are fetched on first use.
"""

from __future__ import annotations

import json
from pathlib import Path

import lancedb
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from pipeline.stages.index import INDEX_VERSION

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX = REPO_ROOT / "index"
CORPUS_MANIFEST = REPO_ROOT / "corpus" / "manifest.json"
API_URL = "https://api.test"
WEB_URL = "https://web.test"
EXPECTED_MOMENTS = 3797
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


def corpus_asset_ids() -> set[str]:
    """Index asset ids are content hashes; the corpus manifest pins them as sha256."""
    manifest = json.loads(CORPUS_MANIFEST.read_text(encoding="utf-8"))
    return {asset["sha256"] for asset in manifest["assets"]}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app(REPO_ROOT, api_url=API_URL, web_url=WEB_URL))


def test_demo_index_holds_every_corpus_asset() -> None:
    db = lancedb.connect(str(INDEX))
    assert {"assets", "moments", "transcripts"} <= set(db.list_tables().tables)

    assets = db.open_table("assets").to_arrow().to_pylist()
    assert {asset["id"] for asset in assets} == corpus_asset_ids()
    for asset in assets:
        assert asset["status"] == "indexed"
        assert asset["index_version"] == INDEX_VERSION
        assert asset["duration_s"] > 0

    moments = db.open_table("moments").to_arrow().to_pylist()
    assert len(moments) == EXPECTED_MOMENTS
    assert {moment["index_version"] for moment in moments} == {INDEX_VERSION}
    assert {moment["kind"] for moment in moments} == {"frame", "shot_start", "transcript"}


def test_demo_index_carries_a_thumbnail_for_every_moment() -> None:
    db = lancedb.connect(str(INDEX))
    moments = db.open_table("moments").to_arrow().to_pylist()
    for moment in moments:
        thumbnail = INDEX / moment["thumbnail"]
        assert thumbnail.is_file(), f"missing thumbnail {moment['thumbnail']}"
        assert thumbnail.read_bytes()[:2] == b"\xff\xd8"


def test_demo_index_declares_its_playback_media() -> None:
    """The committed media manifest pins one proxy per indexed asset."""
    manifest = json.loads((INDEX / "media.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["index_version"] == INDEX_VERSION

    db = lancedb.connect(str(INDEX))
    indexed = {asset["id"] for asset in db.open_table("assets").to_arrow().to_pylist()}
    declared = {asset["asset_id"] for asset in manifest["assets"]}
    assert declared == indexed
    for asset in manifest["assets"]:
        assert asset["path"] == f"{asset['asset_id']}/proxy.mp4"
        assert asset["bytes"] > 0
        assert len(asset["sha256"]) == 64


def test_demo_index_answers_search(client: TestClient) -> None:
    response = client.get("/search", params={"q": "a bridge", "k": 5})
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert results
    for result in results:
        assert set(result) == RESULT_KEYS
        assert result["asset_id"] in corpus_asset_ids()
        assert result["deep_link"].startswith(f"{WEB_URL}/watch/{result['asset_id']}?t=")
        assert result["thumbnail_url"].startswith(f"{API_URL}/media/")
        media = INDEX / result["thumbnail_url"].removeprefix(f"{API_URL}/media/")
        assert media.is_file()


def test_demo_index_serves_media_and_asset_lookup(client: TestClient) -> None:
    asset_id = next(iter(corpus_asset_ids()))
    response = client.get(f"/assets/{asset_id}")
    assert response.status_code == 200, response.text
    asset = response.json()
    assert asset["asset_id"] == asset_id
    assert asset["status"] == "indexed"
    assert asset["proxy_url"] == f"{API_URL}/media/{asset_id}/proxy.mp4"

    thumbnail = next((INDEX / asset_id / "thumbnails").glob("*.jpg"))
    served = client.get(f"/media/{thumbnail.relative_to(INDEX)}")
    assert served.status_code == 200
    assert served.content[:2] == b"\xff\xd8"
