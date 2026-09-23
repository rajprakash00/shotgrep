"""Ship contract: demo playback media packs, fetches, and verifies.

The committed index carries search artifacts and thumbnails but not the
playback proxies (~339 MiB of video); they ship as one release archive. These
tests drive scripts/demo_media.py as a subprocess over synthetic indexes, so
packing, hash verification, extraction, and idempotence are all exercised
without the real corpus or the network.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

from pipeline.stages.index import INDEX_VERSION

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "demo_media.py"


def run_media(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


PROXIES = {"asset-a": b"proxy-a" * 64, "asset-b": b"proxy-b" * 32}


def make_source(tmp_path: Path) -> Path:
    """A work/index lookalike: two assets with proxies plus a table directory."""
    source = tmp_path / "work" / "index"
    for asset_id, proxy in PROXIES.items():
        asset = source / asset_id
        (asset / "thumbnails").mkdir(parents=True)
        (asset / "proxy.mp4").write_bytes(proxy)
        (asset / "thumbnails" / "00000000.jpg").write_bytes(b"\xff\xd8\xff")
    (source / "moments.lance").mkdir()
    return source


def make_index(tmp_path: Path, *, proxies: bool) -> Path:
    """The committed-index lookalike: media manifest and thumbnails, maybe proxies."""
    index = tmp_path / "index"
    for asset_id, proxy in PROXIES.items():
        asset = index / asset_id
        (asset / "thumbnails").mkdir(parents=True)
        (asset / "thumbnails" / "00000000.jpg").write_bytes(b"\xff\xd8\xff")
        if proxies:
            (asset / "proxy.mp4").write_bytes(proxy)
    return index


def pack(tmp_path: Path, source: Path | None = None) -> tuple[Path, Path]:
    source = source or make_source(tmp_path)
    archive = tmp_path / "shotgrep-demo-media-v4.tar"
    manifest = tmp_path / "media.json"
    result = run_media(
        "pack", "--source", str(source), "--out", str(archive), "--manifest", str(manifest)
    )
    assert result.returncode == 0, result.stderr
    return archive, manifest


def test_pack_writes_archive_and_manifest(tmp_path: Path) -> None:
    archive, manifest_path = pack(tmp_path)

    with tarfile.open(archive) as tar:
        assert sorted(tar.getnames()) == ["asset-a/proxy.mp4", "asset-b/proxy.mp4"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["index_version"] == INDEX_VERSION
    assets = {asset["asset_id"]: asset for asset in manifest["assets"]}
    assert set(assets) == set(PROXIES)
    for asset_id, proxy in PROXIES.items():
        assert assets[asset_id]["path"] == f"{asset_id}/proxy.mp4"
        assert assets[asset_id]["bytes"] == len(proxy)
        assert assets[asset_id]["sha256"] == sha256(proxy)


def test_script_index_version_tracks_the_pipeline() -> None:
    """The packer is stdlib-only, so a drift guard keeps its version honest."""
    spec = importlib.util.spec_from_file_location("demo_media", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.INDEX_VERSION == INDEX_VERSION


def test_pack_refuses_an_asset_without_a_proxy(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    (source / "asset-b" / "proxy.mp4").unlink()

    result = run_media(
        "pack",
        "--source",
        str(source),
        "--out",
        str(tmp_path / "media.tar"),
        "--manifest",
        str(tmp_path / "media.json"),
    )
    assert result.returncode != 0
    assert "asset-b" in result.stderr
    assert not (tmp_path / "media.tar").exists()


def test_fetch_restores_proxies_from_a_local_archive(tmp_path: Path) -> None:
    archive, manifest_path = pack(tmp_path)
    index = make_index(tmp_path, proxies=False)

    result = run_media("fetch", "--index", str(index), "--url", str(archive), "--manifest", str(manifest_path))
    assert result.returncode == 0, result.stderr
    for asset_id, proxy in PROXIES.items():
        assert (index / asset_id / "proxy.mp4").read_bytes() == proxy


def test_fetch_is_idempotent(tmp_path: Path) -> None:
    archive, manifest_path = pack(tmp_path)
    index = make_index(tmp_path, proxies=False)

    first = run_media("fetch", "--index", str(index), "--url", str(archive), "--manifest", str(manifest_path))
    assert first.returncode == 0, first.stderr
    before = (index / "asset-a" / "proxy.mp4").stat().st_mtime_ns

    second = run_media("fetch", "--index", str(index), "--url", str(archive), "--manifest", str(manifest_path))
    assert second.returncode == 0, second.stderr
    assert (index / "asset-a" / "proxy.mp4").stat().st_mtime_ns == before


def test_fetch_rejects_a_tampered_archive(tmp_path: Path) -> None:
    _, manifest_path = pack(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tampered = tmp_path / "tampered.tar"
    with tarfile.open(tampered, "w") as tar:
        for asset in manifest["assets"]:
            data = b"evil" * 16
            info = tarfile.TarInfo(asset["path"])
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    index = make_index(tmp_path, proxies=False)

    result = run_media("fetch", "--index", str(index), "--url", str(tampered), "--manifest", str(manifest_path))
    assert result.returncode != 0
    assert "hash" in result.stderr.lower() or "sha256" in result.stderr.lower()
    for asset_id in PROXIES:
        assert not (index / asset_id / "proxy.mp4").exists()


def test_fetch_without_a_manifest_fails(tmp_path: Path) -> None:
    index = make_index(tmp_path, proxies=False)

    result = run_media("fetch", "--index", str(index), "--url", str(tmp_path / "nope.tar"))
    assert result.returncode != 0
    assert "manifest" in result.stderr.lower()


def test_fetch_reports_a_missing_archive_without_a_traceback(tmp_path: Path) -> None:
    _, manifest_path = pack(tmp_path)
    index = make_index(tmp_path, proxies=False)

    result = run_media(
        "fetch", "--index", str(index), "--url", str(tmp_path / "nope.tar"), "--manifest", str(manifest_path)
    )
    assert result.returncode != 0
    assert "error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_optional_fetch_tolerates_a_missing_archive(tmp_path: Path) -> None:
    _, manifest_path = pack(tmp_path)
    index = make_index(tmp_path, proxies=False)

    result = run_media(
        "fetch",
        "--index",
        str(index),
        "--url",
        str(tmp_path / "nope.tar"),
        "--manifest",
        str(manifest_path),
        "--optional",
    )
    assert result.returncode == 0, result.stderr
    assert "warning" in result.stderr.lower()
    assert not (index / "asset-a" / "proxy.mp4").exists()


def test_optional_fetch_still_rejects_a_tampered_archive(tmp_path: Path) -> None:
    _, manifest_path = pack(tmp_path)
    tampered = tmp_path / "tampered.tar"
    with tarfile.open(tampered, "w") as tar:
        data = b"evil" * 16
        info = tarfile.TarInfo("asset-a/proxy.mp4")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    index = make_index(tmp_path, proxies=False)

    result = run_media(
        "fetch",
        "--index",
        str(index),
        "--url",
        str(tampered),
        "--manifest",
        str(manifest_path),
        "--optional",
    )
    assert result.returncode != 0
    assert "sha256" in result.stderr.lower()
    assert not (index / "asset-a" / "proxy.mp4").exists()


def test_verify_reports_missing_and_ok(tmp_path: Path) -> None:
    archive, manifest_path = pack(tmp_path)
    index = make_index(tmp_path, proxies=False)

    missing = run_media("verify", "--index", str(index), "--manifest", str(manifest_path))
    assert missing.returncode != 0
    assert "asset-a" in missing.stderr or "asset-a" in missing.stdout

    fetched = run_media("fetch", "--index", str(index), "--url", str(archive), "--manifest", str(manifest_path))
    assert fetched.returncode == 0, fetched.stderr
    ok = run_media("verify", "--index", str(index), "--manifest", str(manifest_path))
    assert ok.returncode == 0, ok.stderr
    assert "2/2" in ok.stdout
