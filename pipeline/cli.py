"""shotgrep command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipeline.errors import IngestError
from pipeline.ingest import ingest
from pipeline.search import search
from pipeline.stages import STAGES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shotgrep", description="Search video like it's text.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_parser = subparsers.add_parser("ingest", help="ingest a media file into a per-asset manifest")
    ingest_parser.add_argument("input", type=Path, help="media file to ingest")
    ingest_parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("work"),
        help="directory for per-asset artifacts and manifests (default: work)",
    )
    ingest_parser.add_argument(
        "--from-stage",
        choices=[stage.NAME for stage in STAGES],
        metavar="STAGE",
        help="rerun stages from STAGE onward; earlier stages must already be complete",
    )
    search_parser = subparsers.add_parser("search", help="search indexed moments with a natural-language query")
    search_parser.add_argument("query", help="natural-language description of the moment")
    search_parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("work"),
        help="directory holding the index (default: work)",
    )
    search_parser.add_argument(
        "-k",
        type=_positive_int,
        default=5,
        help="number of moments to return (default: 5)",
    )
    serve_parser = subparsers.add_parser("serve", help="serve the REST API over the work directory's index")
    serve_parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("work"),
        help="directory holding the index (default: work)",
    )
    serve_parser.add_argument("--host", default="127.0.0.1", help="interface to bind (default: 127.0.0.1)")
    serve_parser.add_argument("--port", type=int, default=8000, help="port to bind (default: 8000)")
    mcp_parser = subparsers.add_parser("mcp", help="serve the index as MCP tools for coding agents")
    mcp_parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("work"),
        help="directory holding the index (default: work)",
    )
    return parser


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ingest":
        return _ingest(args.input, args.work_dir, args.from_stage)
    if args.command == "search":
        return _search(args.query, args.work_dir, args.k)
    if args.command == "serve":
        return _serve(args.work_dir, args.host, args.port)
    if args.command == "mcp":
        return _mcp(args.work_dir)
    return 2


def _ingest(source: Path, work_dir: Path, from_stage: str | None) -> int:
    try:
        manifest = ingest(source, work_dir, from_stage=from_stage)
    except IngestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"manifest: {manifest.path}")
    print(f"status: {manifest.status}")
    return 0


def _search(query: str, work_dir: Path, k: int) -> int:
    try:
        payload = search(work_dir, query, k=k)
    except IngestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def _serve(work_dir: Path, host: str, port: int) -> int:
    import uvicorn

    from api.app import create_app

    uvicorn.run(create_app(work_dir), host=host, port=port)
    return 0


def _mcp(work_dir: Path) -> int:
    from api.mcp_server import create_mcp
    from api.service import QueryService
    from pipeline.stages.index import INDEX_DIR

    # `serve` mounts the same server over HTTP; stdio is for a local agent.
    create_mcp(QueryService(Path(work_dir) / INDEX_DIR)).run("stdio")
    return 0
