#!/usr/bin/env python3
"""Pack, fetch, and verify the demo playback media.

The committed index carries the search tables, transcripts, and thumbnails, but
not the playback proxies: they are hundreds of megabytes of video. The proxies
ship as one archive attached to the `demo-media-v4` GitHub release, and this
script packs that archive from a built index, fetches it into the committed
index, and verifies every proxy against `index/media.json`. Standard library
only, so a clean machine needs nothing but Python 3.12+.

    python3 scripts/demo_media.py pack
    python3 scripts/demo_media.py fetch
    python3 scripts/demo_media.py verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

REPO = "rajprakash00/shotgrep"
SCHEMA_VERSION = 1
INDEX_VERSION = 4
CHUNK = 1 << 20
USER_AGENT = "shotgrep-demo-media/1.0 (+https://github.com/rajprakash00/shotgrep)"
DEFAULT_SOURCE = Path("work/index")
DEFAULT_INDEX = Path("index")
DEFAULT_MANIFEST = DEFAULT_INDEX / "media.json"
DEFAULT_OUT = Path("dist") / f"shotgrep-demo-media-v{INDEX_VERSION}.tar"
ARCHIVE_NAME = f"shotgrep-demo-media-v{INDEX_VERSION}.tar"
RELEASE_TAG = f"demo-media-v{INDEX_VERSION}"
MEDIA_URL_ENV = "SHOTGREP_DEMO_MEDIA_URL"
PROXY_NAME = "proxy.mp4"
TABLES_SUFFIX = ".lance"


class MediaError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def asset_ids(source: Path) -> list[str]:
    """Asset directories under a built index; LanceDB tables end in .lance."""
    if not source.is_dir():
        raise MediaError(f"{source} is not a directory; build the index first")
    ids = sorted(
        entry.name
        for entry in source.iterdir()
        if entry.is_dir() and not entry.name.endswith(TABLES_SUFFIX)
    )
    if not ids:
        raise MediaError(f"{source} holds no asset directories; build the index first")
    missing = [asset_id for asset_id in ids if not (source / asset_id / PROXY_NAME).is_file()]
    if missing:
        raise MediaError(
            f"{', '.join(missing)} have no {PROXY_NAME}; rebuild the index with the proxy stage complete"
        )
    return ids


def pack(source: Path, out: Path, manifest_path: Path) -> None:
    source = Path(source)
    ids = asset_ids(source)
    entries = [
        {
            "asset_id": asset_id,
            "path": f"{asset_id}/{PROXY_NAME}",
            "bytes": (source / asset_id / PROXY_NAME).stat().st_size,
            "sha256": sha256_file(source / asset_id / PROXY_NAME),
        }
        for asset_id in ids
    ]

    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_suffix(".part")
    total = 0
    with tarfile.open(part, "w") as tar:
        for entry in entries:
            path = source / entry["path"]
            tar.add(path, arcname=entry["path"])
            total += entry["bytes"]
    os.replace(part, out)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {"schema_version": SCHEMA_VERSION, "index_version": INDEX_VERSION, "assets": entries},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"packed {len(entries)} proxies ({_human(total)}) into {out}")
    print(f"wrote {manifest_path}")


def load_manifest(manifest_path: Path) -> list[dict]:
    manifest_path = Path(manifest_path)
    if not manifest_path.is_file():
        raise MediaError(
            f"no media manifest at {manifest_path}; run `python3 scripts/demo_media.py pack` "
            "and commit it with the index"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("assets")
    if not isinstance(entries, list) or not entries:
        raise MediaError(f"{manifest_path} holds no assets")
    for entry in entries:
        path = Path(entry["path"])
        if path.is_absolute() or ".." in path.parts:
            raise MediaError(f"{manifest_path} holds an unsafe path: {entry['path']}")
    return entries


def release_url(tag: str = RELEASE_TAG) -> str:
    url = f"https://api.github.com/repos/{REPO}/releases/tags/{tag}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise MediaError(
            f"cannot resolve the {tag} release: {exc}; set {MEDIA_URL_ENV} to the archive URL"
        ) from exc
    for asset in payload.get("assets", []):
        if asset.get("name") == ARCHIVE_NAME:
            return asset["browser_download_url"]
    raise MediaError(
        f"release {tag} has no {ARCHIVE_NAME}; run `python3 scripts/demo_media.py pack` "
        "and upload the archive as a release asset"
    )


def media_url(url: str | None) -> str:
    return url or os.environ.get(MEDIA_URL_ENV) or release_url()


def download(url: str) -> Path:
    print(f"downloading {url}")
    descriptor, name = tempfile.mkstemp(suffix=".tar")
    path = Path(name)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with os.fdopen(descriptor, "wb") as handle, urllib.request.urlopen(request, timeout=120) as response:
            shutil.copyfileobj(response, handle, CHUNK)
    except (urllib.error.URLError, OSError) as exc:
        path.unlink(missing_ok=True)
        raise MediaError(f"cannot download {url}: {exc}") from exc
    return path


def local_archive(url: str) -> tuple[Path, bool]:
    """A local path or file:// URL is used directly; http(s) is downloaded."""
    if url.startswith("file://"):
        return Path(urllib.request.url2pathname(url[7:])), False
    if "://" not in url:
        return Path(url), False
    return download(url), True


def fetch(index: Path, manifest_path: Path, url: str | None, *, force: bool, optional: bool = False) -> None:
    index = Path(index)
    entries = load_manifest(manifest_path)
    if not force and all(_problem(index, entry) is None for entry in entries):
        print(f"all {len(entries)} proxies already present; nothing to do")
        return

    try:
        archive, temporary = local_archive(media_url(url))
    except MediaError as exc:
        if optional:
            print(f"warning: {exc}; playback will 404", file=sys.stderr)
            return
        raise
    try:
        if not archive.is_file():
            if optional:
                print(f"warning: {archive} is missing; playback will 404", file=sys.stderr)
                return
            raise MediaError(f"archive not found: {archive}")
        _extract(archive, index, entries)
    finally:
        if temporary:
            archive.unlink(missing_ok=True)
    print(f"fetched {len(entries)} proxies into {index}")


def _extract(archive: Path, index: Path, entries: list[dict]) -> None:
    if not tarfile.is_tarfile(archive):
        raise MediaError(f"cannot read {archive}: not a tar archive")
    with tarfile.open(archive) as tar:
        for entry in entries:
            target = index / entry["path"]
            if _problem(index, entry) is None:
                continue
            member = _member(tar, entry["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            part = target.with_name(target.name + ".part")
            try:
                source = tar.extractfile(member)
                if source is None:
                    raise MediaError(f"{archive} member {entry['path']} is not a regular file")
                with source, part.open("wb") as handle:
                    digest = _hash_copy(source, handle)
                if digest != entry["sha256"]:
                    raise MediaError(f"{entry['path']}: sha256 mismatch; the archive is corrupt or stale")
                os.replace(part, target)
            except Exception:
                part.unlink(missing_ok=True)
                raise


def _hash_copy(source, handle) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = source.read(CHUNK)
        if not chunk:
            break
        digest.update(chunk)
        handle.write(chunk)
    return digest.hexdigest()


def _member(tar: tarfile.TarFile, path: str) -> tarfile.TarInfo:
    try:
        return tar.getmember(path)
    except KeyError as exc:
        raise MediaError(f"the archive has no {path}") from exc


def _problem(index: Path, entry: dict) -> str | None:
    """None when the proxy matches the manifest; otherwise the reason it does not."""
    target = index / entry["path"]
    if not target.is_file():
        return "missing (run `python3 scripts/demo_media.py fetch`)"
    if target.stat().st_size != entry["bytes"] or sha256_file(target) != entry["sha256"]:
        return "sha256 mismatch"
    return None


def verify(index: Path, manifest_path: Path) -> int:
    index = Path(index)
    entries = load_manifest(manifest_path)
    problems = []
    for entry in entries:
        problem = _problem(index, entry)
        if problem is not None:
            problems.append((entry, problem))
    for entry, problem in problems:
        print(f"error: {entry['path']}: {problem}", file=sys.stderr)
    print(f"verify: {len(entries) - len(problems)}/{len(entries)} proxies ok")
    return 1 if problems else 0


def _human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GiB"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pack, fetch, and verify the demo playback media.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pack_parser = subparsers.add_parser("pack", help="archive the proxies from a built index")
    pack_parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="built index (default: work/index)")
    pack_parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"archive path (default: {DEFAULT_OUT})")
    pack_parser.add_argument(
        "--manifest", type=Path, default=DEFAULT_MANIFEST, help=f"media manifest path (default: {DEFAULT_MANIFEST})"
    )

    fetch_parser = subparsers.add_parser("fetch", help="download the media archive into the committed index")
    fetch_parser.add_argument("--index", type=Path, default=DEFAULT_INDEX, help="index directory (default: index)")
    fetch_parser.add_argument("--url", help=f"archive URL or path (default: ${MEDIA_URL_ENV}, then the GitHub release)")
    fetch_parser.add_argument("--manifest", type=Path, help="media manifest path (default: INDEX/media.json)")
    fetch_parser.add_argument("--force", action="store_true", help="re-extract even when proxies already match")
    fetch_parser.add_argument(
        "--optional",
        action="store_true",
        help="warn instead of failing when the archive is unavailable; a corrupt archive still fails",
    )

    verify_parser = subparsers.add_parser("verify", help="check every proxy against the media manifest")
    verify_parser.add_argument("--index", type=Path, default=DEFAULT_INDEX, help="index directory (default: index)")
    verify_parser.add_argument("--manifest", type=Path, help="media manifest path (default: INDEX/media.json)")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "pack":
            pack(args.source, args.out, args.manifest)
            return 0
        if args.command == "fetch":
            manifest = args.manifest or args.index / "media.json"
            fetch(args.index, manifest, args.url, force=args.force, optional=args.optional)
            return 0
        if args.command == "verify":
            manifest = args.manifest or args.index / "media.json"
            return verify(args.index, manifest)
    except MediaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
