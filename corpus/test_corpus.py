"""Tests for the corpus fetch/verify tool and the committed manifest."""

from __future__ import annotations

import hashlib
import http.server
import re
import struct
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

import fetch

CORPUS_DIR = Path(__file__).resolve().parent


def build_mp4(duration_s: float = 2.0, timescale: int = 1000, version: int = 0) -> bytes:
    def atom(typ: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", 8 + len(payload)) + typ + payload

    if version == 0:
        header = b"\x00\x00\x00\x00"
        body = struct.pack(">II", 0, 0) + struct.pack(">II", timescale, int(duration_s * timescale))
    else:
        header = b"\x01\x00\x00\x00"
        body = struct.pack(">QQ", 0, 0) + struct.pack(">I", timescale) + struct.pack(">Q", int(duration_s * timescale))
    ftyp = atom(b"ftyp", b"isom" + struct.pack(">I", 0x200) + b"isomiso2avc1mp41")
    moov = atom(b"moov", atom(b"mvhd", header + body))
    return ftyp + moov


def ebml_vint(value: int) -> bytes:
    for length in range(1, 9):
        if value < (1 << (7 * length)) - 1:
            return ((1 << (7 * length)) | value).to_bytes(length, "big")
    raise ValueError("value too large")


def ebml_element(element_id: int, payload: bytes) -> bytes:
    id_length = max(1, (element_id.bit_length() + 7) // 8)
    return element_id.to_bytes(id_length, "big") + ebml_vint(len(payload)) + payload


def build_mkv(duration_s: float = 3.0, timecode_scale_ns: int = 1_000_000, unknown_segment_size: bool = False) -> bytes:
    duration_units = duration_s * 1_000_000_000 / timecode_scale_ns
    info = ebml_element(
        0x1549A966,
        ebml_element(0x2AD7B1, timecode_scale_ns.to_bytes(3, "big"))
        + ebml_element(0x4489, struct.pack(">f", duration_units)),
    )
    segment_id = 0x18538067.to_bytes(4, "big")
    if unknown_segment_size:
        segment = segment_id + b"\x01\xff\xff\xff\xff\xff\xff\xff" + info
    else:
        segment = segment_id + ebml_vint(len(info)) + info
    header = ebml_element(0x1A45DFA3, b"\x42\x86\x81\x01\x42\xf7\x81\x01")
    return header + segment


def write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


class DurationParserTests(unittest.TestCase):
    def test_mp4_version_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "clip.m4v", build_mp4(duration_s=12.5))
            self.assertAlmostEqual(fetch.mp4_duration_s(path), 12.5, places=3)

    def test_mp4_version_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "clip.mov", build_mp4(duration_s=61.25, version=1))
            self.assertAlmostEqual(fetch.mp4_duration_s(path), 61.25, places=3)

    def test_mp4_garbage_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "clip.mp4", b"not a video" * 100)
            self.assertIsNone(fetch.mp4_duration_s(path))

    def test_mkv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "clip.mkv", build_mkv(duration_s=3.0))
            self.assertAlmostEqual(fetch.mkv_duration_s(path), 3.0, places=3)

    def test_mkv_unknown_segment_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "clip.mkv", build_mkv(duration_s=4.5, unknown_segment_size=True))
            self.assertAlmostEqual(fetch.mkv_duration_s(path), 4.5, places=3)

    def test_container_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertAlmostEqual(fetch.container_duration_s(write(Path(tmp) / "a.mp4", build_mp4())), 2.0, places=3)
            self.assertAlmostEqual(
                fetch.container_duration_s(write(Path(tmp) / "b.mkv", build_mkv())), 3.0, places=3
            )
            self.assertIsNone(fetch.container_duration_s(write(Path(tmp) / "c.webm", b"\x00" * 32)))


class VerifyAssetTests(unittest.TestCase):
    def _asset(self, path: Path, **overrides):
        data = path.read_bytes()
        asset = {
            "id": "clip",
            "filename": path.name,
            "container": path.suffix.lstrip("."),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "duration_s": 2.0,
        }
        asset.update(overrides)
        return asset

    def test_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "clip.mp4", build_mp4(duration_s=2.0))
            self.assertEqual(fetch.verify_asset(self._asset(path), Path(tmp)), [])

    def test_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            asset = {"id": "clip", "filename": "clip.mp4", "container": "mp4"}
            problems = fetch.verify_asset(asset, Path(tmp))
            self.assertTrue(any("missing" in p for p in problems))

    def test_corrupt_and_size_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "clip.mp4", build_mp4())
            asset = self._asset(path, sha256="0" * 64, bytes=1)
            problems = fetch.verify_asset(asset, Path(tmp))
            self.assertTrue(any("size" in p for p in problems))
            self.assertTrue(any("sha256" in p for p in problems))

    def test_duration_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "clip.mp4", build_mp4(duration_s=2.0))
            problems = fetch.verify_asset(self._asset(path, duration_s=99.0), Path(tmp))
            self.assertTrue(any("duration" in p for p in problems))

    def test_duration_unparseable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "clip.mp4", b"garbage" * 100)
            asset = self._asset(path)
            problems = fetch.verify_asset(asset, Path(tmp))
            self.assertTrue(any("duration" in p for p in problems))


class _RangeHandler(http.server.BaseHTTPRequestHandler):
    server_version = "CorpusTest/1.0"

    def do_GET(self):
        root = self.server.root  # type: ignore[attr-defined]
        data = (root / self.path.lstrip("/")).read_bytes()
        rng = self.headers.get("Range")
        start = 0
        status = 200
        if rng:
            match = re.match(r"bytes=(\d+)-(\d*)$", rng)
            if match:
                start = int(match.group(1))
                status = 206
                self.server.range_requests += 1  # type: ignore[attr-defined]
        body = data[start:]
        self.send_response(status)
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class _Server:
    def __init__(self, root: Path):
        self.root = root
        handler = _RangeHandler
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.httpd.root = root  # type: ignore[attr-defined]
        self.httpd.range_requests = 0  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


class DownloadTests(unittest.TestCase):
    def test_download_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = bytes(range(256)) * 4096
            (root / "clip.bin").write_bytes(data)
            server = _Server(root)
            try:
                dest = root / "out" / "clip.bin"
                fetch.download(f"{server.url}/clip.bin", dest, sha256=hashlib.sha256(data).hexdigest(), size=len(data))
                self.assertEqual(dest.read_bytes(), data)
                self.assertFalse(dest.with_suffix(dest.suffix + ".part").exists())
            finally:
                server.close()

    def test_download_resumes_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = bytes(range(256)) * 4096
            (root / "clip.bin").write_bytes(data)
            server = _Server(root)
            try:
                dest = root / "clip.bin"
                dest.with_suffix(".bin.part").write_bytes(data[:1000])
                fetch.download(f"{server.url}/clip.bin", dest, sha256=hashlib.sha256(data).hexdigest(), size=len(data))
                self.assertEqual(dest.read_bytes(), data)
                self.assertEqual(server.httpd.range_requests, 1)  # type: ignore[attr-defined]
            finally:
                server.close()

    def test_download_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "clip.bin").write_bytes(b"hello")
            server = _Server(root)
            try:
                with self.assertRaises(fetch.FetchError):
                    fetch.download(
                        f"{server.url}/clip.bin", root / "out.bin", sha256="0" * 64, size=5, retries=1, log=lambda *_: None
                    )
            finally:
                server.close()


class FetchAssetTests(unittest.TestCase):
    def _serve_zip(self, root: Path, archive_member: str, member: bytes) -> None:
        with zipfile.ZipFile(root / "film.zip", "w") as zf:
            zf.writestr(archive_member, member)

    def test_fetch_zip_asset_extracts_and_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            member = build_mp4(duration_s=2.0)
            self._serve_zip(source, "film.m4v", member)
            server = _Server(source)
            try:
                media = root / "media"
                asset = {
                    "id": "film",
                    "filename": "film.m4v",
                    "container": "mp4",
                    "source_url": f"{server.url}/film.zip",
                    "archive_member": "film.m4v",
                    "archive_bytes": (source / "film.zip").stat().st_size,
                    "archive_sha256": hashlib.sha256((source / "film.zip").read_bytes()).hexdigest(),
                    "bytes": len(member),
                    "sha256": hashlib.sha256(member).hexdigest(),
                    "duration_s": 2.0,
                }
                fetch.fetch_asset(asset, media, log=lambda *_: None)
                self.assertEqual((media / "film.m4v").read_bytes(), member)
                self.assertFalse((media / ".archives" / "film.zip").exists())
            finally:
                server.close()

    def test_fetch_direct_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            member = build_mp4(duration_s=2.0)
            (source / "film.mp4").write_bytes(member)
            server = _Server(source)
            try:
                media = root / "media"
                asset = {
                    "id": "film",
                    "filename": "film.mp4",
                    "container": "mp4",
                    "source_url": f"{server.url}/film.mp4",
                    "archive_member": None,
                    "bytes": len(member),
                    "sha256": hashlib.sha256(member).hexdigest(),
                    "duration_s": 2.0,
                }
                fetch.fetch_asset(asset, media, log=lambda *_: None)
                self.assertEqual((media / "film.mp4").read_bytes(), member)
            finally:
                server.close()


class LicenseVerificationTests(unittest.TestCase):
    def _manifest(self, quote: str) -> dict:
        return {
            "assets": [
                {
                    "id": "clip",
                    "license_evidence_url": "https://example.test/license",
                    "license_evidence_quote": quote,
                }
            ]
        }

    def test_quote_present(self):
        page = "<html><body>The film is licensed as <b>Creative Commons Attribution 3.0</b>.</body></html>"
        problems = fetch.verify_licenses(
            self._manifest("Creative Commons Attribution 3.0"), fetch_text=lambda url: page, log=lambda *_: None
        )
        self.assertEqual(problems, [])

    def test_quote_missing(self):
        page = "<html><body>All rights reserved.</body></html>"
        problems = fetch.verify_licenses(
            self._manifest("Creative Commons Attribution 3.0"), fetch_text=lambda url: page, log=lambda *_: None
        )
        self.assertEqual(len(problems), 1)

    def test_smart_quotes_normalize(self):
        page = "licensed as \u201cCreative Commons Attribution\u00a02.5\u201d today"
        problems = fetch.verify_licenses(
            self._manifest("Creative Commons Attribution 2.5"), fetch_text=lambda url: page, log=lambda *_: None
        )
        self.assertEqual(problems, [])


class CommittedManifestTests(unittest.TestCase):
    REQUIRED = (
        "id",
        "title",
        "author",
        "license",
        "license_url",
        "license_evidence_url",
        "license_evidence_quote",
        "source_url",
        "filename",
        "container",
        "duration_s",
        "bytes",
        "sha256",
        "attribution",
    )
    LICENSES = ("CC-BY-2.5", "CC-BY-3.0", "CC-BY-4.0", "CC0-1.0")

    @classmethod
    def setUpClass(cls):
        cls.manifest = fetch.load_manifest(CORPUS_DIR / "manifest.json")

    def test_required_fields_and_pinned_values(self):
        self.assertGreaterEqual(len(self.manifest["assets"]), 3)
        filenames = set()
        for asset in self.manifest["assets"]:
            for key in self.REQUIRED:
                self.assertIn(key, asset, f"{asset.get('id')} missing {key}")
                self.assertTrue(asset[key] not in (None, ""), f"{asset.get('id')} has empty {key}")
            self.assertRegex(asset["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(asset["bytes"], 0)
            self.assertGreater(asset["duration_s"], 0)
            self.assertIn(asset["license"], self.LICENSES)
            self.assertTrue(asset["source_url"].startswith("https://"))
            self.assertNotIn(asset["filename"], filenames)
            filenames.add(asset["filename"])

    def test_attribution_names_title_and_license(self):
        for asset in self.manifest["assets"]:
            self.assertIn("CC BY", asset["attribution"])
            self.assertIn(asset["title"], asset["attribution"])

    def test_media_dir_is_gitignored(self):
        gitignore = (CORPUS_DIR.parent / ".gitignore").read_text()
        self.assertIn("corpus/media/", gitignore)


class AttributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = fetch.load_manifest(CORPUS_DIR / "manifest.json")
        cls.attribution = (CORPUS_DIR / "ATTRIBUTION.md").read_text()
        cls.readme = (CORPUS_DIR.parent / "README.md").read_text()

    def test_every_asset_credited(self):
        for asset in self.manifest["assets"]:
            self.assertIn(asset["title"], self.attribution)
            self.assertIn(asset["license"], self.attribution)
            self.assertIn(asset["attribution"], self.attribution)

    def test_readme_carries_the_same_lines(self):
        for asset in self.manifest["assets"]:
            self.assertIn(asset["attribution"], self.readme)

    def test_licenses_are_cc(self):
        self.assertIn("creativecommons.org/licenses", self.attribution)


if __name__ == "__main__":
    unittest.main()
