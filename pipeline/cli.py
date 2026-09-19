"""shotgrep command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.errors import IngestError
from pipeline.ingest import ingest


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ingest":
        return _ingest(args.input, args.work_dir)
    return 2


def _ingest(source: Path, work_dir: Path) -> int:
    try:
        manifest = ingest(source, work_dir)
    except IngestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"manifest: {manifest.path}")
    print(f"status: {manifest.status}")
    return 0
