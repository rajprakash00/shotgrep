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
        type=int,
        default=5,
        help="number of moments to return (default: 5)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ingest":
        return _ingest(args.input, args.work_dir, args.from_stage)
    if args.command == "search":
        return _search(args.query, args.work_dir, args.k)
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
