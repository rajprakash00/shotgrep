"""Ingest CLI contract: fixture in, complete manifest out.

Drives `shotgrep ingest` as a subprocess over the committed fixture clip and
asserts only external behavior (exit code, manifest bytes, artifact contents),
per SPEC.md: stage internals get no tests. ffprobe (FFmpeg) must be on PATH.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "clip.mp4"
FIXTURE_SHA256 = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()


def run_ingest(input_path: Path, work_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pipeline", "ingest", str(input_path), "--work-dir", str(work_dir)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def manifest_path(work_dir: Path) -> Path:
    found = sorted(Path(work_dir).glob("*/manifest.json"))
    assert len(found) == 1, f"expected one manifest under {work_dir}, found {found}"
    return found[0]


def read_manifest(work_dir: Path) -> dict:
    return json.loads(manifest_path(work_dir).read_text(encoding="utf-8"))


def test_ingest_probes_fixture(tmp_path: Path) -> None:
    result = run_ingest(FIXTURE, tmp_path / "work")
    assert result.returncode == 0, result.stderr

    manifest = read_manifest(tmp_path / "work")
    assert manifest["schema_version"] == 1
    assert manifest["status"] == "complete"

    asset = manifest["asset"]
    assert asset["id"] == FIXTURE_SHA256
    assert asset["filename"] == "clip.mp4"
    assert asset["bytes"] == FIXTURE.stat().st_size

    probe = manifest["stages"]["probe"]
    assert probe["status"] == "complete"
    assert probe["error"] is None
    assert probe["outputs"]["codec"] == "h264"
    assert probe["outputs"]["fps"] == pytest.approx(24.0, abs=0.01)
    assert probe["outputs"]["duration_s"] == pytest.approx(10.0, abs=0.1)

    artifact = manifest_path(tmp_path / "work").parent / probe["outputs"]["artifact"]
    assert json.loads(artifact.read_text(encoding="utf-8")) == {
        "codec": "h264",
        "duration_s": probe["outputs"]["duration_s"],
        "fps": probe["outputs"]["fps"],
    }


def test_rerun_is_byte_identical(tmp_path: Path) -> None:
    work = tmp_path / "work"
    first = run_ingest(FIXTURE, work)
    assert first.returncode == 0, first.stderr
    path = manifest_path(work)
    before = path.read_bytes()

    second = run_ingest(FIXTURE, work)
    assert second.returncode == 0, second.stderr
    assert path.read_bytes() == before


def test_missing_input_fails_without_manifest(tmp_path: Path) -> None:
    work = tmp_path / "work"
    result = run_ingest(tmp_path / "nope.mp4", work)
    assert result.returncode != 0
    assert "nope.mp4" in result.stderr
    assert list(work.glob("*/manifest.json")) == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses file permissions")
def test_unreadable_input_fails_without_manifest(tmp_path: Path) -> None:
    work = tmp_path / "work"
    unreadable = tmp_path / "unreadable.mp4"
    unreadable.write_bytes(FIXTURE.read_bytes())
    unreadable.chmod(0)
    try:
        result = run_ingest(unreadable, work)
    finally:
        unreadable.chmod(0o644)
    assert result.returncode != 0
    assert "unreadable.mp4" in result.stderr
    assert list(work.glob("*/manifest.json")) == []


def test_corrupt_manifest_fails_cleanly(tmp_path: Path) -> None:
    work = tmp_path / "work"
    manifest = work / FIXTURE_SHA256 / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{not json", encoding="utf-8")

    result = run_ingest(FIXTURE, work)

    assert result.returncode != 0
    assert "not valid JSON" in result.stderr
    assert manifest.read_text(encoding="utf-8") == "{not json"
