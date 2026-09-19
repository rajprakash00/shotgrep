#!/usr/bin/env python3
"""Fetch and verify the shotgrep corpus.

The committed manifest pins each film's SHA-256, size, and container duration.
This script downloads the media into corpus/media/ (gitignored), verifies it
against the manifest, and can re-verify or re-pin the manifest. Standard
library only, so a clean machine needs nothing but Python 3.12+.

    python3 corpus/fetch.py                  # download anything missing/invalid
    python3 corpus/fetch.py --check          # verify local files, no network
    python3 corpus/fetch.py --verify-licenses
    python3 corpus/fetch.py --update         # download then re-pin the manifest
"""

from __future__ import annotations

import argparse
import hashlib
import html
import http.client
import json
import os
import re
import shutil
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = CORPUS_DIR / "manifest.json"
DEFAULT_MEDIA_DIR = CORPUS_DIR / "media"
CHUNK = 1 << 20
USER_AGENT = "shotgrep-corpus-fetcher/1.0 (+https://github.com/rajprakash00/shotgrep)"
DURATION_TOLERANCE_S = 1.0
MP4_SUFFIXES = {".mp4", ".m4v", ".mov"}
MKV_SUFFIXES = {".mkv", ".webm"}


class FetchError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_atoms(handle, end: int):
    while handle.tell() + 8 <= end:
        pos = handle.tell()
        header = handle.read(8)
        if len(header) < 8:
            return
        size, kind = struct.unpack(">I4s", header)
        header_size = 8
        if size == 1:
            large = handle.read(8)
            if len(large) < 8:
                return
            size = struct.unpack(">Q", large)[0]
            header_size = 16
        elif size == 0:
            size = end - pos
        if size < header_size or pos + size > end:
            return
        yield kind, pos, size, header_size
        handle.seek(pos + size)


def _mvhd_duration(handle, payload_pos: int, payload_size: int) -> float | None:
    handle.seek(payload_pos)
    data = handle.read(min(payload_size, 128))
    if len(data) < 4:
        return None
    version = data[0]
    if version == 0:
        if len(data) < 20:
            return None
        timescale, duration = struct.unpack(">II", data[12:20])
    elif version == 1:
        if len(data) < 32:
            return None
        timescale, duration = struct.unpack(">IQ", data[20:32])
    else:
        return None
    if not timescale:
        return None
    return duration / timescale


def mp4_duration_s(path: Path) -> float | None:
    size = path.stat().st_size
    with path.open("rb") as handle:
        for kind, pos, atom_size, header_size in _iter_atoms(handle, size):
            if kind != b"moov":
                continue
            moov_end = pos + atom_size
            for child_kind, child_pos, child_size, child_header in _iter_atoms(handle, moov_end):
                if child_kind == b"mvhd":
                    return _mvhd_duration(handle, child_pos + child_header, child_size - child_header)
    return None


def _read_ebml_id(handle, end: int) -> int | None:
    if handle.tell() + 1 > end:
        return None
    first = handle.read(1)
    if not first:
        return None
    length = 1
    mask = 0x80
    while not first[0] & mask:
        mask >>= 1
        length += 1
        if length > 4 or mask == 0:
            return None
    rest = handle.read(length - 1)
    if len(rest) < length - 1:
        return None
    value = first[0]
    for byte in rest:
        value = (value << 8) | byte
    return value


def _read_ebml_size(handle) -> tuple[int | None, bool]:
    first = handle.read(1)
    if not first:
        return None, False
    length = 1
    mask = 0x80
    while not first[0] & mask:
        mask >>= 1
        length += 1
        if length > 8 or mask == 0:
            return None, False
    value = first[0] & (mask - 1)
    rest = handle.read(length - 1)
    if len(rest) < length - 1:
        return None, False
    for byte in rest:
        value = (value << 8) | byte
    return value, value == (1 << (7 * length)) - 1


def _mkv_info_duration(handle, end: int) -> float | None:
    timecode_scale = 1_000_000
    duration_units: float | None = None
    while handle.tell() < end:
        element_id = _read_ebml_id(handle, end)
        if element_id is None:
            break
        element_size, unknown = _read_ebml_size(handle)
        if element_size is None:
            break
        payload_pos = handle.tell()
        if element_id == 0x2AD7B1 and not unknown:
            timecode_scale = int.from_bytes(handle.read(element_size), "big")
        elif element_id == 0x4489 and not unknown:
            raw = handle.read(element_size)
            if element_size == 4:
                duration_units = struct.unpack(">f", raw)[0]
            elif element_size == 8:
                duration_units = struct.unpack(">d", raw)[0]
        if unknown:
            break
        handle.seek(payload_pos + element_size)
    if duration_units is None:
        return None
    return duration_units * timecode_scale / 1e9


def mkv_duration_s(path: Path) -> float | None:
    size = path.stat().st_size
    with path.open("rb") as handle:
        if _read_ebml_id(handle, size) != 0x1A45DFA3:
            return None
        header_size, unknown = _read_ebml_size(handle)
        if header_size is None or unknown:
            return None
        handle.seek(header_size, os.SEEK_CUR)
        if _read_ebml_id(handle, size) != 0x18538067:
            return None
        segment_size, unknown = _read_ebml_size(handle)
        if segment_size is None:
            return None
        segment_end = size if unknown else min(handle.tell() + segment_size, size)
        while handle.tell() < segment_end:
            element_id = _read_ebml_id(handle, segment_end)
            if element_id is None:
                return None
            element_size, unknown = _read_ebml_size(handle)
            if element_size is None:
                return None
            if element_id == 0x1549A966:
                info_end = segment_end if unknown else handle.tell() + element_size
                return _mkv_info_duration(handle, info_end)
            if unknown:
                return None
            handle.seek(handle.tell() + element_size)
    return None


def container_duration_s(path: Path) -> float | None:
    suffix = path.suffix.lower()
    if suffix in MP4_SUFFIXES:
        return mp4_duration_s(path)
    if suffix in MKV_SUFFIXES:
        return mkv_duration_s(path)
    return None


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def save_manifest(manifest: dict, path: Path = MANIFEST_PATH) -> None:
    text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    Path(path).write_text(text, encoding="utf-8")


def archive_filename(asset: dict) -> str:
    return Path(urllib.parse.urlparse(asset["source_url"]).path).name


def archive_path(asset: dict, media_dir: Path) -> Path | None:
    if not asset.get("archive_member"):
        return None
    return Path(media_dir) / ".archives" / archive_filename(asset)


def _pinned_problems(path: Path, expected_bytes: int | None, expected_sha256: str | None) -> list[str]:
    problems = []
    if expected_bytes is not None and path.stat().st_size != expected_bytes:
        problems.append(f"size mismatch: expected {expected_bytes}, got {path.stat().st_size}")
    if expected_sha256 and sha256_file(path) != expected_sha256:
        problems.append("sha256 mismatch")
    return problems


def verify_asset(asset: dict, media_dir: Path) -> list[str]:
    path = Path(media_dir) / asset["filename"]
    if not path.is_file():
        return [f"missing file {path}"]
    problems = _pinned_problems(path, asset.get("bytes"), asset.get("sha256"))
    if problems:
        return problems
    expected_duration = asset.get("duration_s")
    if expected_duration is not None:
        actual = container_duration_s(path)
        if actual is None:
            problems.append(f"could not parse duration from {path.name}")
        elif abs(actual - expected_duration) > DURATION_TOLERANCE_S:
            problems.append(f"duration mismatch: expected {expected_duration:.3f}s, got {actual:.3f}s")
    return problems


def _archive_problems(asset: dict, path: Path) -> list[str]:
    if not path.is_file():
        return ["missing archive"]
    return _pinned_problems(path, asset.get("archive_bytes"), asset.get("archive_sha256"))


def download(
    url: str,
    dest: Path,
    *,
    sha256: str | None = None,
    size: int | None = None,
    retries: int = 4,
    timeout: int = 120,
    log=print,
) -> None:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        resume_from = part.stat().st_size if part.exists() else 0
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            if resume_from:
                request.add_header("Range", f"bytes={resume_from}-")
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if resume_from and response.status != 206:
                    resume_from = 0
                    part.unlink(missing_ok=True)
                mode = "ab" if resume_from else "wb"
                with part.open(mode) as handle:
                    while True:
                        chunk = response.read(CHUNK)
                        if not chunk:
                            break
                        handle.write(chunk)
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError, OSError) as exc:
            last_error = exc
            log(f"  attempt {attempt}/{retries} failed: {exc}")
            time.sleep(min(2**attempt, 30))
            continue
        problems = _pinned_problems(part, size, sha256)
        if problems:
            part.unlink(missing_ok=True)
            last_error = FetchError("; ".join(problems))
            log(f"  attempt {attempt}/{retries} verification failed: {'; '.join(problems)}")
            time.sleep(min(2**attempt, 30))
            continue
        os.replace(part, dest)
        return
    raise FetchError(f"download failed after {retries} attempts: {url}: {last_error}")


def fetch_asset(asset: dict, media_dir: Path, *, keep_archives: bool = False, log=print) -> None:
    media_dir = Path(media_dir)
    dest = media_dir / asset["filename"]
    if not verify_asset(asset, media_dir):
        log(f"{asset['id']}: ok")
        return
    log(f"{asset['id']}: fetching {asset['source_url']}")
    if asset.get("archive_member"):
        archive = archive_path(asset, media_dir)
        if archive is None:
            raise FetchError(f"{asset['id']}: archive path could not be derived")
        if _archive_problems(asset, archive):
            if archive.exists():
                archive.unlink()
            archive.parent.mkdir(parents=True, exist_ok=True)
            download(
                asset["source_url"],
                archive,
                sha256=asset.get("archive_sha256"),
                size=asset.get("archive_bytes"),
                log=log,
            )
        with zipfile.ZipFile(archive) as zf:
            if asset["archive_member"] not in zf.namelist():
                raise FetchError(f"{asset['id']}: {asset['archive_member']} not found in {archive.name}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            temp = dest.with_name(dest.name + ".part")
            with zf.open(asset["archive_member"]) as source, temp.open("wb") as handle:
                shutil.copyfileobj(source, handle, CHUNK)
            os.replace(temp, dest)
        if not keep_archives:
            archive.unlink()
    else:
        download(asset["source_url"], dest, sha256=asset.get("sha256"), size=asset.get("bytes"), log=log)
    problems = verify_asset(asset, media_dir)
    if problems:
        dest.unlink(missing_ok=True)
        raise FetchError(f"{asset['id']}: verification failed: {'; '.join(problems)}")
    log(f"{asset['id']}: ok")


def pin_asset(asset: dict, media_dir: Path) -> None:
    path = Path(media_dir) / asset["filename"]
    duration = container_duration_s(path)
    if duration is None:
        raise FetchError(f"{asset['id']}: cannot determine duration of {path.name}")
    asset["bytes"] = path.stat().st_size
    asset["sha256"] = sha256_file(path)
    asset["duration_s"] = round(duration, 3)


def normalize_text(value: str) -> str:
    value = html.unescape(value)
    value = (
        value.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u00a0", " ")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )
    return re.sub(r"\s+", " ", value).strip().casefold()


def html_to_text(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style).*?</\1>", " ", markup)
    markup = re.sub(r"(?s)<[^>]+>", " ", markup)
    return normalize_text(markup)


def _http_text(url: str, timeout: int = 60) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except (urllib.error.URLError, http.client.HTTPException, OSError) as exc:
        raise FetchError(f"cannot fetch {url}: {exc}") from exc


def verify_licenses(manifest: dict, *, fetch_text=None, log=print) -> list[str]:
    fetch_text = fetch_text or _http_text
    problems = []
    for asset in manifest["assets"]:
        url = asset["license_evidence_url"]
        try:
            text = html_to_text(fetch_text(url))
        except FetchError as exc:
            problems.append(f"{asset['id']}: {exc}")
            continue
        if normalize_text(asset["license_evidence_quote"]) not in text:
            problems.append(f"{asset['id']}: license quote not found at {url}")
        else:
            log(f"{asset['id']}: license evidence ok ({url})")
    return problems


def _select_assets(manifest: dict, only: list[str]) -> list[dict]:
    if not only:
        return manifest["assets"]
    wanted = set(only)
    known = {asset["id"] for asset in manifest["assets"]}
    unknown = wanted - known
    if unknown:
        raise FetchError(f"unknown asset id(s): {', '.join(sorted(unknown))}")
    return [asset for asset in manifest["assets"] if asset["id"] in wanted]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch and verify the shotgrep corpus.")
    parser.add_argument("--only", action="append", default=[], metavar="ID", help="limit to one asset id (repeatable)")
    parser.add_argument("--check", action="store_true", help="verify local files only; no downloads")
    parser.add_argument("--verify-licenses", action="store_true", help="fetch license evidence pages and check quotes")
    parser.add_argument("--update", action="store_true", help="download, then re-pin hashes/sizes/durations in the manifest")
    parser.add_argument("--keep-archives", action="store_true", help="keep downloaded zip archives")
    args = parser.parse_args(argv)

    manifest = load_manifest()
    media_dir = DEFAULT_MEDIA_DIR
    try:
        assets = _select_assets(manifest, args.only)
    except FetchError as exc:
        parser.error(str(exc))

    if args.verify_licenses:
        problems = verify_licenses({"assets": assets})
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        print(f"license verification: {len(assets) - len(problems)}/{len(assets)} ok")
        return 1 if problems else 0

    if args.check:
        failed = 0
        for asset in assets:
            problems = verify_asset(asset, media_dir)
            if problems:
                failed += 1
                print(f"{asset['id']}: {'; '.join(problems)}", file=sys.stderr)
            else:
                print(f"{asset['id']}: ok")
        print(f"check: {len(assets) - failed}/{len(assets)} ok")
        return 1 if failed else 0

    if args.update:
        for asset in assets:
            fetch_asset(asset, media_dir, keep_archives=True, log=print)
            pin_asset(asset, media_dir)
            archive = archive_path(asset, media_dir)
            if archive and archive.is_file():
                asset["archive_bytes"] = archive.stat().st_size
                asset["archive_sha256"] = sha256_file(archive)
                if not args.keep_archives:
                    archive.unlink()
        save_manifest(manifest)
        print(f"pinned {len(assets)} asset(s) in {MANIFEST_PATH}")
        return 0

    unpinned = [asset["id"] for asset in assets if not asset.get("sha256")]
    if unpinned:
        parser.error(f"manifest is not pinned for: {', '.join(unpinned)} (run with --update)")

    failed = 0
    for asset in assets:
        try:
            fetch_asset(asset, media_dir, keep_archives=args.keep_archives, log=print)
        except FetchError as exc:
            failed += 1
            print(f"error: {exc}", file=sys.stderr)
    print(f"fetch: {len(assets) - failed}/{len(assets)} ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
