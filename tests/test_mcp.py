"""Read contract: MCP tools are thin wrappers over the same query service.

One ingest of the fixture clip is shared by the module; every test drives the
MCP server through an in-memory client and compares its results with the REST
API over the same index. The stdio test then connects a real MCP client to
`shotgrep mcp` as a subprocess, the way a local coding agent does. ffprobe
(FFmpeg) must be on PATH; SigLIP int8 assets are fetched on first use.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from mcp import Client, StdioServerParameters
from mcp.server import MCPServer

from api.app import create_app
from api.mcp_server import create_mcp
from api.service import DEFAULT_K, MAX_K, QueryService

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "clip.mp4"
FIXTURE_SHA256 = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
API_URL = "https://api.test"
WEB_URL = "https://web.test"
TOOL_NAMES = {"search_moments", "get_moment", "get_transcript", "list_assets"}
TEST_ENV = {
    "SHOTGREP_ASR_MODEL": "tiny",
    "SHOTGREP_ASR_DEVICE": "cpu",
    "SHOTGREP_EMBED_MODEL": "Xenova/siglip-base-patch16-224",
    "SHOTGREP_EMBED_PRECISION": "int8",
}
ENV = {**os.environ, **TEST_ENV}
URL_ENV = {"SHOTGREP_API_URL": API_URL, "SHOTGREP_WEB_URL": WEB_URL}


def run_cli(command: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pipeline", command, *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=ENV,
    )


@pytest.fixture(scope="module")
def work_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    work = tmp_path_factory.mktemp("mcp") / "work"
    result = run_cli("ingest", str(FIXTURE), "--work-dir", str(work))
    assert result.returncode == 0, result.stderr
    return work


@pytest.fixture(scope="module")
def server(work_dir: Path) -> MCPServer:
    service = QueryService(work_dir / "index", api_url=API_URL, web_url=WEB_URL)
    return create_mcp(service)


@pytest.fixture(scope="module")
def rest(work_dir: Path) -> TestClient:
    return TestClient(create_app(work_dir, api_url=API_URL, web_url=WEB_URL))


def rest_json(rest: TestClient, path: str, **params: object) -> dict:
    response = rest.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def error_text(result) -> str:
    return " ".join(block.text for block in result.content if getattr(block, "type", None) == "text")


async def call(client: Client, name: str, arguments: dict) -> dict:
    result = await client.call_tool(name, arguments)
    assert not result.is_error, error_text(result)
    return result.structured_content


@pytest.mark.anyio
async def test_tools_publish_validated_schemas(server: MCPServer) -> None:
    async with Client(server) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    assert set(tools) == TOOL_NAMES
    for name, tool in tools.items():
        assert tool.description, name
        Draft202012Validator.check_schema(tool.input_schema)
        assert tool.output_schema is not None, name
        Draft202012Validator.check_schema(tool.output_schema)

    search = tools["search_moments"]
    assert search.input_schema["required"] == ["query"]
    properties = search.input_schema["properties"]
    assert properties["query"]["type"] == "string"
    assert properties["k"]["minimum"] == 1
    assert properties["k"]["maximum"] == MAX_K
    assert properties["k"]["default"] == DEFAULT_K
    for name in ("asset", "start_s", "end_s"):
        assert "anyOf" in properties[name], properties[name]

    validator = Draft202012Validator(search.input_schema)
    validator.validate({"query": "a bridge"})
    validator.validate({"query": "a bridge", "k": 3, "asset": "a" * 64, "start_s": 1.0, "end_s": 2.0})
    for invalid in ({"q": "a bridge"}, {"query": "a bridge", "k": 0}, {"query": "a bridge", "k": MAX_K + 1}):
        with pytest.raises(ValidationError):
            validator.validate(invalid)

    assert tools["get_moment"].input_schema["required"] == ["moment_id"]
    assert tools["get_transcript"].input_schema["required"] == ["asset_id"]
    assert tools["list_assets"].input_schema.get("properties", {}) == {}
    assert "deep_link" in tools["get_moment"].output_schema["properties"]
    moments = search.output_schema["$defs"]["Moment"]["properties"]
    assert moments["kind"]["enum"] == ["shot_start", "frame", "transcript"]
    assert {"$ref"} <= set(search.output_schema["properties"]["results"]["items"])


@pytest.mark.anyio
async def test_search_tool_matches_rest(server: MCPServer, rest: TestClient) -> None:
    async with Client(server) as client:
        unfiltered = await call(client, "search_moments", {"query": "robotics", "k": 3})
        filtered = await call(
            client,
            "search_moments",
            {"query": "robotics", "asset": FIXTURE_SHA256, "start_s": 2.0, "end_s": 4.0, "k": 5},
        )
    assert unfiltered == rest_json(rest, "/search", q="robotics", k=3)
    assert filtered == rest_json(
        rest, "/search", q="robotics", asset=FIXTURE_SHA256, start_s=2.0, end_s=4.0, k=5
    )
    assert filtered["results"], "expected the time-range filter to keep visual moments"


@pytest.mark.anyio
async def test_get_moment_matches_rest(server: MCPServer, rest: TestClient) -> None:
    moment_id = f"{FIXTURE_SHA256}-transcript-00004440"
    async with Client(server) as client:
        moment = await call(client, "get_moment", {"moment_id": moment_id})
    assert moment == rest_json(rest, f"/moments/{moment_id}")
    assert moment["moment_id"] == moment_id
    assert moment["kind"] == "transcript"
    assert moment["score"] is None
    assert moment["deep_link"] == f"{WEB_URL}/watch/{FIXTURE_SHA256}?t=4.44"


@pytest.mark.anyio
async def test_get_transcript_matches_rest(server: MCPServer, rest: TestClient) -> None:
    async with Client(server) as client:
        payload = await call(
            client,
            "get_transcript",
            {"asset_id": FIXTURE_SHA256, "start_s": 1.5, "end_s": 4.5},
        )
    assert payload == rest_json(
        rest, f"/assets/{FIXTURE_SHA256}/transcript", start_s=1.5, end_s=4.5
    )
    assert len(payload["segments"]) == 2
    words = payload["segments"][0]["words"]
    assert words and all({"word", "start_s", "end_s"} == set(word) for word in words)


@pytest.mark.anyio
async def test_list_assets_matches_rest(server: MCPServer, rest: TestClient) -> None:
    async with Client(server) as client:
        payload = await call(client, "list_assets", {})
    assert payload == rest_json(rest, "/assets")
    assert [asset["asset_id"] for asset in payload["assets"]] == [FIXTURE_SHA256]
    assert payload["assets"][0]["filename"] == "clip.mp4"
    assert payload["assets"][0]["proxy_url"] == f"{API_URL}/media/{FIXTURE_SHA256}/proxy.mp4"


@pytest.mark.anyio
async def test_unknown_ids_are_tool_errors(server: MCPServer) -> None:
    async with Client(server) as client:
        moment = await client.call_tool("get_moment", {"moment_id": "not-a-moment"})
        transcript = await client.call_tool("get_transcript", {"asset_id": "not-an-asset"})
    assert moment.is_error and "not-a-moment" in error_text(moment)
    assert transcript.is_error and "not-an-asset" in error_text(transcript)


@pytest.mark.anyio
async def test_missing_index_is_a_clean_tool_error(tmp_path: Path) -> None:
    server = create_mcp(QueryService(tmp_path / "index", api_url=API_URL, web_url=WEB_URL))
    async with Client(server) as client:
        result = await client.call_tool("list_assets", {})
    assert result.is_error
    assert "index" in error_text(result).lower()


@pytest.mark.anyio
async def test_a_compound_request_can_be_answered_from_tool_results(server: MCPServer) -> None:
    # "Find robotics, then the nearest bridge": search, quote the candidate's
    # transcript range, then search again and pick the closest moment by time.
    async with Client(server) as client:
        hits = await call(client, "search_moments", {"query": "robotics space", "k": 5})
        candidate = next(hit for hit in hits["results"] if hit["kind"] == "transcript")
        moment = await call(client, "get_moment", {"moment_id": candidate["moment_id"]})
        transcript = await call(
            client,
            "get_transcript",
            {"asset_id": moment["asset_id"], "start_s": moment["start_s"], "end_s": moment["end_s"]},
        )
        bridges = await call(
            client,
            "search_moments",
            {"query": "two people standing on a bridge", "asset": moment["asset_id"], "k": 5},
        )
        nearest = min(bridges["results"], key=lambda hit: abs(hit["start_s"] - moment["start_s"]))
        near = await call(client, "get_moment", {"moment_id": nearest["moment_id"]})

    assert {key: value for key, value in moment.items() if key != "score"} == {
        key: value for key, value in candidate.items() if key != "score"
    }
    assert candidate["score"] is not None
    assert moment["score"] is None
    assert moment["deep_link"].startswith(f"{WEB_URL}/watch/{moment['asset_id']}?t=")
    assert moment["thumbnail_url"].startswith(f"{API_URL}/media/")
    assert transcript["segments"], "expected speech in the candidate's range"
    spoken = " ".join(segment["text"] for segment in transcript["segments"]).lower()
    assert "robotics" in spoken
    for segment in transcript["segments"]:
        assert segment["end_s"] > segment["start_s"]
        assert segment["words"], "quoting requires word timestamps"
        for word in segment["words"]:
            assert word["start_s"] >= segment["start_s"] - 0.01
            assert word["end_s"] <= segment["end_s"] + 0.01

    assert nearest["start_s"] == 3.0, "the bridge frame at 3s is the nearest bridge to the robotics speech"
    assert near["moment_id"] == nearest["moment_id"]
    assert near["deep_link"].startswith(f"{WEB_URL}/watch/{nearest['asset_id']}?t=3")


@pytest.mark.anyio
async def test_shotgrep_mcp_serves_the_same_tools_over_stdio(work_dir: Path) -> None:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "pipeline", "mcp", "--work-dir", str(work_dir)],
        env={**ENV, **URL_ENV},
        cwd=REPO_ROOT,
    )
    async with Client(parameters) as client:
        tools = {tool.name for tool in (await client.list_tools()).tools}
        assets = await call(client, "list_assets", {})
        hits = await call(client, "search_moments", {"query": "robotics", "k": 1})
        moment = await call(client, "get_moment", {"moment_id": hits["results"][0]["moment_id"]})
    assert tools == TOOL_NAMES
    assert [asset["asset_id"] for asset in assets["assets"]] == [FIXTURE_SHA256]
    assert moment["moment_id"] == hits["results"][0]["moment_id"]
    assert moment["deep_link"].startswith(f"{WEB_URL}/watch/{FIXTURE_SHA256}?t=")


@pytest.mark.anyio
async def test_serve_exposes_mcp_beside_rest(work_dir: Path) -> None:
    # One process serves both surfaces: the API app mounts the MCP endpoint.
    app = create_app(work_dir, api_url=API_URL, web_url=WEB_URL)
    uvicorn_server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=uvicorn_server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not uvicorn_server.started:
            assert time.monotonic() < deadline, "uvicorn did not start"
            time.sleep(0.05)
        port = uvicorn_server.servers[0].sockets[0].getsockname()[1]
        async with Client(f"http://127.0.0.1:{port}/mcp") as client:
            tools = {tool.name for tool in (await client.list_tools()).tools}
            assets = await call(client, "list_assets", {})
    finally:
        uvicorn_server.should_exit = True
        thread.join(timeout=10)
    assert tools == TOOL_NAMES
    assert [asset["asset_id"] for asset in assets["assets"]] == [FIXTURE_SHA256]
