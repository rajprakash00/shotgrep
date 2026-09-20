"""Ingest CLI contract: fixture in, complete manifest out.

Drives `shotgrep ingest` as a subprocess over the committed fixture clip and
asserts only external behavior (exit code, manifest bytes, artifact contents),
per SPEC.md: stage internals get no tests. ffprobe (FFmpeg) must be on PATH.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import lancedb
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "clip.mp4"
FIXTURE_SHA256 = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
# Contract tests exercise the ASR and embedding seams cheaply and hermetically:
# a tiny model on the CPU, and the pinned SigLIP int8 pair. The production
# defaults are large-v3 with automatic CUDA detection and the same SigLIP repo.
TEST_ENV = {
    "SHOTGREP_ASR_MODEL": "tiny",
    "SHOTGREP_ASR_DEVICE": "cpu",
    "SHOTGREP_EMBED_MODEL": "Xenova/siglip-base-patch16-224",
    "SHOTGREP_EMBED_PRECISION": "int8",
}


def run_ingest(
    input_path: Path,
    work_dir: Path,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pipeline", "ingest", str(input_path), "--work-dir", str(work_dir), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**os.environ, **TEST_ENV, **(env or {})},
    )


def manifest_path(work_dir: Path) -> Path:
    found = sorted(Path(work_dir).glob("*/manifest.json"))
    assert len(found) == 1, f"expected one manifest under {work_dir}, found {found}"
    return found[0]


def read_manifest(work_dir: Path) -> dict:
    return json.loads(manifest_path(work_dir).read_text(encoding="utf-8"))


def read_artifact(work_dir: Path, name: str) -> bytes:
    return (manifest_path(work_dir).parent / name).read_bytes()


def read_transcript(work_dir: Path) -> dict:
    return json.loads(read_artifact(work_dir, "transcript.json"))


def transcript_words(transcript: dict) -> list[dict]:
    return [word for segment in transcript["segments"] for word in segment["words"]]


def transcript_shape(value: object) -> object:
    """Structure only: dict keys and element types, ignoring list lengths and scalar values."""
    if isinstance(value, dict):
        return {key: transcript_shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [transcript_shape(value[0])] if value else []
    return type(value).__name__


def ffprobe_json(path: Path) -> dict:
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def assert_playable_proxy(path: Path, *, duration_s: float | None = None, has_audio: bool = True) -> None:
    probe = ffprobe_json(path)
    video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
    assert video["codec_name"] == "h264"
    assert video["pix_fmt"] == "yuv420p"
    if has_audio:
        audio = next(stream for stream in probe["streams"] if stream["codec_type"] == "audio")
        assert audio["codec_name"] == "aac"
    assert "mp4" in probe["format"]["format_name"].split(",")
    if duration_s is not None:
        assert float(probe["format"]["duration"]) == pytest.approx(duration_s, abs=0.1)
    data = path.read_bytes()
    assert data.find(b"moov") != -1
    assert data.find(b"moov") < data.find(b"mdat"), "moov must precede mdat for browser streaming"


SHIM_TEMPLATE = """#!/bin/sh
case "$*" in
{case}esac
exec {ffmpeg} "$@"
"""
HIDE_HW_CASE = """  *-encoders*)
    {ffmpeg} -encoders | grep -v h264_nvenc
    exit 0
    ;;
"""
BREAK_HW_CASE = """  *h264_nvenc*)
    echo "h264_nvenc unavailable" >&2
    exit 1
    ;;
"""


def env_with_ffmpeg_shim(tmp_path: Path, case: str) -> dict[str, str]:
    real_ffmpeg = shutil.which("ffmpeg")
    assert real_ffmpeg is not None, "FFmpeg must be on PATH"
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    shim = shim_dir / "ffmpeg"
    shim.write_text(
        SHIM_TEMPLATE.format(case=case, ffmpeg=shlex.quote(real_ffmpeg)),
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return {**os.environ, "PATH": f"{shim_dir}{os.pathsep}{os.environ['PATH']}"}


def write_odd_clip(path: Path) -> None:
    width, height = 321, 241
    ppm = path.with_suffix(".ppm")
    ppm.write_bytes(b"P6\n%d %d\n255\n" % (width, height) + bytes([64]) * (width * height * 3))
    completed = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-i",
            str(ppm),
            "-t",
            "1",
            "-r",
            "10",
            "-c:v",
            "ffv1",
            "-pix_fmt",
            "bgr0",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


@functools.lru_cache(maxsize=1)
def nvenc_works() -> bool:
    if shutil.which("ffmpeg") is None:
        return False
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=black:s=320x240:d=0.2",
        "-c:v",
        "h264_nvenc",
        "-f",
        "null",
        "-",
    ]
    return subprocess.run(command, capture_output=True).returncode == 0


@functools.lru_cache(maxsize=1)
def cuda_works() -> bool:
    import ctranslate2

    if ctranslate2.get_cuda_device_count() == 0:
        return False
    from pipeline.models.transcriber import FasterWhisperTranscriber

    return FasterWhisperTranscriber(model="tiny", device="cuda").transcribe(FIXTURE).device == "cuda"


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


def test_proxy_and_shots_stages_complete(tmp_path: Path) -> None:
    work = tmp_path / "work"
    result = run_ingest(FIXTURE, work)
    assert result.returncode == 0, result.stderr

    manifest = read_manifest(work)
    assert manifest["status"] == "complete"
    for stage in ("proxy", "shots"):
        assert manifest["stages"][stage]["status"] == "complete"
        assert manifest["stages"][stage]["error"] is None
    assert manifest["stages"]["proxy"]["outputs"]["artifact"] == "proxy.mp4"
    assert manifest["stages"]["shots"]["outputs"]["artifact"] == "shots.json"
    assert manifest["stages"]["shots"]["outputs"]["count"] >= 2

    assert_playable_proxy(manifest_path(work).parent / "proxy.mp4", duration_s=10.0)
    shots = json.loads(read_artifact(work, "shots.json"))["shots"]
    assert len(shots) >= 2
    assert [shot["index"] for shot in shots] == list(range(len(shots)))
    assert shots[0]["start_s"] == 0.0
    for previous, current in zip(shots, shots[1:], strict=False):
        assert current["start_s"] == previous["end_s"]
    assert shots[-1]["end_s"] == pytest.approx(10.0, abs=0.1)


def test_resume_from_shots_skips_probe_and_proxy(tmp_path: Path) -> None:
    work = tmp_path / "work"
    first = run_ingest(FIXTURE, work)
    assert first.returncode == 0, first.stderr
    directory = manifest_path(work).parent
    before = read_manifest(work)
    probe_bytes = read_artifact(work, "probe.json")
    proxy_bytes = read_artifact(work, "proxy.mp4")
    shots_bytes = read_artifact(work, "shots.json")
    probe_mtime = (directory / "probe.json").stat().st_mtime_ns
    proxy_mtime = (directory / "proxy.mp4").stat().st_mtime_ns

    second = run_ingest(FIXTURE, work, "--from-stage", "shots")
    assert second.returncode == 0, second.stderr

    after = read_manifest(work)
    assert after["status"] == "complete"
    assert after["stages"]["probe"] == before["stages"]["probe"]
    assert after["stages"]["proxy"] == before["stages"]["proxy"]
    assert read_artifact(work, "probe.json") == probe_bytes
    assert read_artifact(work, "proxy.mp4") == proxy_bytes
    assert read_artifact(work, "shots.json") == shots_bytes
    assert (directory / "probe.json").stat().st_mtime_ns == probe_mtime
    assert (directory / "proxy.mp4").stat().st_mtime_ns == proxy_mtime


def test_from_stage_requires_earlier_stages(tmp_path: Path) -> None:
    work = tmp_path / "work"
    result = run_ingest(FIXTURE, work, "--from-stage", "shots")
    assert result.returncode != 0
    assert "probe" in result.stderr
    assert list(work.glob("*/manifest.json")) == []


@pytest.mark.parametrize(
    ("case", "expect_fallback"),
    [(HIDE_HW_CASE, False), (BREAK_HW_CASE, True)],
    ids=["no-hardware-encoder", "broken-hardware-encoder"],
)
def test_cpu_proxy_when_hardware_unavailable(tmp_path: Path, case: str, expect_fallback: bool) -> None:
    env = env_with_ffmpeg_shim(tmp_path, case)
    work = tmp_path / "work"
    result = run_ingest(FIXTURE, work, env=env)
    assert result.returncode == 0, result.stderr

    manifest = read_manifest(work)
    outputs = manifest["stages"]["proxy"]["outputs"]
    assert outputs["encoder"] == "libx264"
    if expect_fallback:
        assert "h264_nvenc" in outputs["fallback_reason"]
    else:
        assert "fallback_reason" not in outputs
    assert manifest["status"] == "complete"
    assert_playable_proxy(manifest_path(work).parent / "proxy.mp4", duration_s=10.0)


@pytest.mark.skipif(not nvenc_works(), reason="no working h264_nvenc on this machine")
def test_hardware_proxy_when_available(tmp_path: Path) -> None:
    work = tmp_path / "work"
    result = run_ingest(FIXTURE, work)
    assert result.returncode == 0, result.stderr

    outputs = read_manifest(work)["stages"]["proxy"]["outputs"]
    assert outputs["encoder"] == "h264_nvenc"
    assert "fallback_reason" not in outputs
    assert_playable_proxy(manifest_path(work).parent / "proxy.mp4", duration_s=10.0)


def test_proxy_normalizes_odd_source_dimensions(tmp_path: Path) -> None:
    source = tmp_path / "odd.mkv"
    write_odd_clip(source)
    source_stream = next(
        stream for stream in ffprobe_json(source)["streams"] if stream["codec_type"] == "video"
    )
    assert source_stream["width"] % 2 == 1 and source_stream["height"] % 2 == 1

    work = tmp_path / "work"
    result = run_ingest(source, work)
    assert result.returncode == 0, result.stderr

    proxy = manifest_path(work).parent / "proxy.mp4"
    proxy_stream = next(stream for stream in ffprobe_json(proxy)["streams"] if stream["codec_type"] == "video")
    assert proxy_stream["width"] % 2 == 0
    assert proxy_stream["height"] % 2 == 0
    assert_playable_proxy(proxy, duration_s=1.0, has_audio=False)


def test_asr_stage_transcribes_fixture_with_word_timestamps(tmp_path: Path) -> None:
    work = tmp_path / "work"
    result = run_ingest(FIXTURE, work)
    assert result.returncode == 0, result.stderr

    manifest = read_manifest(work)
    assert manifest["status"] == "complete"
    asr = manifest["stages"]["asr"]
    assert asr["status"] == "complete"
    assert asr["error"] is None
    assert asr["outputs"]["artifact"] == "transcript.json"
    assert asr["outputs"]["model"] == "tiny"
    assert asr["outputs"]["device"] == "cpu"
    assert asr["outputs"]["words"] > 0

    transcript = read_transcript(work)
    words = transcript_words(transcript)
    assert len(words) == asr["outputs"]["words"]
    assert len(transcript["segments"]) == asr["outputs"]["segments"]
    assert transcript["language"] == "en"
    for word in words:
        assert set(word) == {"word", "start_s", "end_s"}
        assert 0.0 <= word["start_s"] <= word["end_s"] <= 10.1
    starts = [word["start_s"] for word in words]
    assert starts == sorted(starts)
    spoken = {word["word"].strip(".,!?;:").lower() for word in words}
    assert {"jerk", "robotics", "space"} <= spoken


def test_cpu_path_produces_same_transcript_shape(tmp_path: Path) -> None:
    cpu_work = tmp_path / "cpu"
    auto_work = tmp_path / "auto"
    cpu_run = run_ingest(FIXTURE, cpu_work, env={"SHOTGREP_ASR_DEVICE": "cpu"})
    auto_run = run_ingest(FIXTURE, auto_work, env={"SHOTGREP_ASR_DEVICE": "auto"})
    assert cpu_run.returncode == 0, cpu_run.stderr
    assert auto_run.returncode == 0, auto_run.stderr

    assert read_manifest(cpu_work)["stages"]["asr"]["outputs"]["device"] == "cpu"
    cpu_transcript = read_transcript(cpu_work)
    auto_transcript = read_transcript(auto_work)
    assert set(cpu_transcript) == {"compute_type", "device", "language", "language_probability", "model", "segments"}
    assert transcript_words(cpu_transcript)
    assert transcript_shape(cpu_transcript) == transcript_shape(auto_transcript)


def test_cuda_request_without_a_device_falls_back_to_cpu(tmp_path: Path) -> None:
    work = tmp_path / "work"
    env = {"SHOTGREP_ASR_DEVICE": "cuda", "CUDA_VISIBLE_DEVICES": ""}
    result = run_ingest(FIXTURE, work, env=env)
    assert result.returncode == 0, result.stderr

    manifest = read_manifest(work)
    assert manifest["status"] == "complete"
    outputs = manifest["stages"]["asr"]["outputs"]
    assert outputs["device"] == "cpu"
    assert "cuda" in outputs["fallback_reason"].lower()
    assert transcript_words(read_transcript(work))


@pytest.mark.skipif(not cuda_works(), reason="no working CUDA device on this machine")
def test_cuda_transcription_when_available(tmp_path: Path) -> None:
    work = tmp_path / "work"
    result = run_ingest(FIXTURE, work, env={"SHOTGREP_ASR_DEVICE": "auto"})
    assert result.returncode == 0, result.stderr

    outputs = read_manifest(work)["stages"]["asr"]["outputs"]
    assert outputs["device"] == "cuda"
    assert "fallback_reason" not in outputs
    assert transcript_words(read_transcript(work))


def test_asr_stage_is_idempotent(tmp_path: Path) -> None:
    work = tmp_path / "work"
    first = run_ingest(FIXTURE, work)
    assert first.returncode == 0, first.stderr
    transcript = manifest_path(work).parent / "transcript.json"
    before = read_artifact(work, "transcript.json")
    transcript_mtime = transcript.stat().st_mtime_ns

    second = run_ingest(FIXTURE, work)
    assert second.returncode == 0, second.stderr
    assert read_artifact(work, "transcript.json") == before
    assert transcript.stat().st_mtime_ns == transcript_mtime

    third = run_ingest(FIXTURE, work, "--from-stage", "asr")
    assert third.returncode == 0, third.stderr
    assert read_artifact(work, "transcript.json") == before
    manifest = read_manifest(work)
    assert manifest["status"] == "complete"
    assert manifest["stages"]["asr"]["status"] == "complete"


def test_asset_without_audio_gets_empty_transcript(tmp_path: Path) -> None:
    source = tmp_path / "silent.mkv"
    write_odd_clip(source)
    work = tmp_path / "work"
    result = run_ingest(source, work)
    assert result.returncode == 0, result.stderr

    manifest = read_manifest(work)
    assert manifest["status"] == "complete"
    outputs = manifest["stages"]["asr"]["outputs"]
    assert outputs["artifact"] == "transcript.json"
    assert outputs["segments"] == 0
    assert outputs["words"] == 0

    transcript = read_transcript(work)
    assert transcript["segments"] == []
    assert transcript["language"] is None


def read_frames(work_dir: Path) -> dict:
    return json.loads(read_artifact(work_dir, "frames.json"))


def index_rows(work_dir: Path, table: str) -> list[dict]:
    db = lancedb.connect(str(manifest_path(work_dir).parent.parent / "index"))
    rows = db.open_table(table).to_arrow().to_pylist()
    return sorted(rows, key=lambda row: row["id"])


def test_frames_stage_samples_one_fps_shots_and_transcript(tmp_path: Path) -> None:
    work = tmp_path / "work"
    result = run_ingest(FIXTURE, work)
    assert result.returncode == 0, result.stderr

    manifest = read_manifest(work)
    assert manifest["status"] == "complete"
    stage = manifest["stages"]["frames"]
    assert stage["status"] == "complete"
    assert stage["error"] is None
    assert stage["outputs"]["artifact"] == "frames.json"

    samples = read_frames(work)["samples"]
    assert len(samples) == stage["outputs"]["count"]
    times = [sample["time_s"] for sample in samples]
    assert times == sorted(times)
    assert len(set(times)) == len(times)

    kinds = {kind for sample in samples for kind in sample["kinds"]}
    assert kinds == {"frame", "shot_start", "transcript"}
    sampled = {kind: {sample["time_s"] for sample in samples if kind in sample["kinds"]} for kind in kinds}
    assert sampled["frame"] >= {1.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0}
    shots = json.loads(read_artifact(work, "shots.json"))["shots"]
    assert sampled["shot_start"] == {shot["start_s"] for shot in shots}
    transcript = read_transcript(work)
    assert sampled["transcript"] == {segment["start_s"] for segment in transcript["segments"]}

    directory = manifest_path(work).parent
    for sample in samples:
        assert sample["thumbnail"] == f"thumbnails/{round(sample['time_s'] * 1000):08d}.jpg"
        thumbnail = directory / sample["thumbnail"]
        assert thumbnail.is_file(), f"missing thumbnail {sample['thumbnail']}"
        assert thumbnail.read_bytes()[:2] == b"\xff\xd8"


def test_embed_stage_embeds_every_frame_sample(tmp_path: Path) -> None:
    work = tmp_path / "work"
    result = run_ingest(FIXTURE, work)
    assert result.returncode == 0, result.stderr

    manifest = read_manifest(work)
    stage = manifest["stages"]["embed"]
    assert stage["status"] == "complete"
    assert stage["error"] is None
    outputs = stage["outputs"]
    assert outputs["artifact"] == "embeddings.npy"
    assert outputs["precision"] == "int8"
    assert outputs["dimension"] == 768
    assert outputs["model"]
    assert outputs["revision"]

    embeddings = np.load(manifest_path(work).parent / "embeddings.npy")
    samples = read_frames(work)["samples"]
    assert outputs["count"] == len(samples)
    assert embeddings.shape == (len(samples), outputs["dimension"])
    assert embeddings.dtype == np.float32
    assert np.allclose(np.linalg.norm(embeddings, axis=1), 1.0, atol=1e-3)


def test_index_stage_holds_moments_of_every_kind(tmp_path: Path) -> None:
    work = tmp_path / "work"
    result = run_ingest(FIXTURE, work)
    assert result.returncode == 0, result.stderr

    manifest = read_manifest(work)
    stage = manifest["stages"]["index"]
    assert stage["status"] == "complete"
    assert stage["error"] is None
    assert stage["outputs"]["index"] == "index"
    assert stage["outputs"]["assets"] == 1

    rows = index_rows(work, "moments")
    assert len(rows) == stage["outputs"]["moments"]
    assert {row["kind"] for row in rows} == {"frame", "shot_start", "transcript"}
    assert {row["asset_id"] for row in rows} == {FIXTURE_SHA256}
    embed = manifest["stages"]["embed"]["outputs"]
    for row in rows:
        assert len(row["embedding"]) == 768
        assert (manifest_path(work).parent.parent / row["thumbnail"]).is_file()
        assert row["embedding_model"] == embed["model"]
        assert row["embedding_precision"] == embed["precision"]
        assert row["embedding_revision"] == embed["revision"]

    assets = index_rows(work, "assets")
    assert [row["id"] for row in assets] == [FIXTURE_SHA256]
    assert assets[0]["filename"] == "clip.mp4"
    assert assets[0]["status"] == "indexed"
    assert assets[0]["codec"] == "h264"
    assert assets[0]["fps"] == pytest.approx(24.0, abs=0.01)
    assert assets[0]["duration_s"] == pytest.approx(10.0, abs=0.1)


def test_rerun_embed_and_index_is_idempotent(tmp_path: Path) -> None:
    work = tmp_path / "work"
    first = run_ingest(FIXTURE, work)
    assert first.returncode == 0, first.stderr
    before = read_manifest(work)
    embeddings = read_artifact(work, "embeddings.npy")
    frames = read_artifact(work, "frames.json")
    moments = index_rows(work, "moments")
    assets = index_rows(work, "assets")

    second = run_ingest(FIXTURE, work, "--from-stage", "embed")
    assert second.returncode == 0, second.stderr
    after = read_manifest(work)
    assert after["status"] == "complete"
    assert after["stages"]["embed"]["outputs"] == before["stages"]["embed"]["outputs"]
    assert after["stages"]["index"]["outputs"] == before["stages"]["index"]["outputs"]
    assert read_artifact(work, "embeddings.npy") == embeddings
    assert read_artifact(work, "frames.json") == frames
    assert index_rows(work, "moments") == moments
    assert index_rows(work, "assets") == assets

    third = run_ingest(FIXTURE, work, "--from-stage", "index")
    assert third.returncode == 0, third.stderr
    assert read_manifest(work)["stages"]["index"]["outputs"] == before["stages"]["index"]["outputs"]
    assert index_rows(work, "moments") == moments
