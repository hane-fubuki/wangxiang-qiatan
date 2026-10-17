"""Portable downloads are a fixed authenticated endpoint, never a file browser."""
import hashlib
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from app import create_server
from backend.releases import Releases, ReleaseUnavailable, MAX_RELEASE_BYTES
from backend.remote_access import COOKIE_NAME, MAX_RESPONSE, create_remote_server
from tests.test_server import FakeGateway


FILENAME = "wisdom-tavern-20261016-windows-x64.zip"


def publish(directory, payload):
    directory.mkdir(exist_ok=True)
    (directory / FILENAME).write_bytes(payload)
    manifest = {"filename": FILENAME, "version": "2026.10.16", "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest()}
    (directory / "latest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def small_zip():
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("readme.txt", "Synthetic package, no user files.")
    return data.getvalue()


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "releases"
        self.manifest = publish(self.directory, small_zip())
        self.releases = Releases(self.directory)

    def test_only_safe_metadata_is_returned_and_package_is_verified(self):
        self.manifest["secret"] = "never return extra manifest fields"
        (self.directory / "latest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        info, stream = self.releases.open_latest()
        with stream:
            self.assertEqual(hashlib.sha256(stream.read()).hexdigest(), info["sha256"])
        self.assertEqual(set(info), {"filename", "version", "size", "sha256", "url"})
        self.assertEqual(info["url"], "/downloads/latest.zip")

    def test_manifest_traversal_names_sizes_and_injection_are_rejected(self):
        for changes in ({"filename": "../.env"}, {"filename": "C:\\private.zip"},
                        {"filename": FILENAME + '\"\r\nX-Test: bad'}, {"filename": "other.zip"},
                        {"size": True}, {"size": MAX_RELEASE_BYTES + 1}, {"size": self.manifest["size"] + 1},
                        {"sha256": "f" * 64}, {"sha256": "not a hash"}, {"version": "unsafe\nvalue"}):
            with self.subTest(changes=changes):
                (self.directory / "latest.json").write_text(json.dumps({**self.manifest, **changes}), encoding="utf-8")
                with self.assertRaises(ReleaseUnavailable):
                    self.releases.open_latest()

    def test_symlink_file_manifest_or_directory_is_rejected(self):
        for link in (self.directory, self.directory / "latest.json", self.directory / FILENAME):
            with self.subTest(link=link), patch.object(Path, "is_symlink", lambda path: path == link):
                with self.assertRaises(ReleaseUnavailable):
                    self.releases.open_latest()

    def test_missing_malformed_and_nonzip_packages_are_unavailable(self):
        for manifest in ("{", "[]", " " * 4097):
            with self.subTest(manifest=manifest[:10]):
                (self.directory / "latest.json").write_text(manifest, encoding="utf-8")
                with self.assertRaises(ReleaseUnavailable):
                    self.releases.open_latest()
        publish(self.directory, b"this is not a zip")
        with self.assertRaises(ReleaseUnavailable):
            self.releases.open_latest()
        (self.directory / "latest.json").unlink()
        with self.assertRaises(ReleaseUnavailable):
            self.releases.open_latest()


class ReleaseHTTPTests(unittest.TestCase):
    HOST = "downloads-tests.example"
    PASSWORD = "test-password-never-used-outside-tests"

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.directory = cls.root / "releases"
        cls.directory.mkdir()
        target = cls.directory / FILENAME
        # A real ZIP exceeds the existing 32 MiB response cap. Stream both its
        # creation and retrieval so this regression test needs little memory.
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
            with archive.open("synthetic.bin", "w") as output:
                for _ in range(33):
                    output.write(b"download transport test\x00".ljust(1024 * 1024, b"x"))
        digest = hashlib.sha256()
        with target.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        cls.manifest = {"filename": FILENAME, "version": "2026.10.16", "size": target.stat().st_size,
                        "sha256": digest.hexdigest()}
        (cls.directory / "latest.json").write_text(json.dumps(cls.manifest), encoding="utf-8")
        cls.server = create_server(0, data_dir=cls.root / "data", gateway=FakeGateway(), releases_dir=cls.directory)
        cls.proxy = create_remote_server(0, cls.server.server_port, cls.HOST, cls.PASSWORD)
        cls.threads = []
        for server in (cls.server, cls.proxy):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            cls.threads.append(thread)

    @classmethod
    def tearDownClass(cls):
        for server, thread in zip((cls.server, cls.proxy), cls.threads):
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        cls.temp.cleanup()

    def request(self, path, *, remote=False, login=False, digest=False):
        server = self.proxy if remote else self.server
        headers = {"Host": self.HOST} if remote else {}
        if remote and login:
            status, token = self.proxy.auth.login(self.PASSWORD)
            self.assertEqual(status, 200)
            headers["Cookie"] = COOKIE_NAME + "=" + token
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
        try:
            conn.request("GET", path, headers=headers)
            response = conn.getresponse()
            result_headers = dict(response.getheaders())
            if digest:
                result = hashlib.sha256()
                count = 0
                while chunk := response.read(1024 * 1024):
                    count += len(chunk)
                    result.update(chunk)
                payload = {"size": count, "sha256": result.hexdigest()}
            else:
                payload = response.read()
            return response.status, result_headers, payload
        finally:
            conn.close()

    def test_local_and_authenticated_remote_download_complete_above_32_mib(self):
        self.assertGreater(self.manifest["size"], MAX_RESPONSE)
        for remote in (False, True):
            with self.subTest(remote=remote):
                status, headers, body = self.request("/downloads/latest.zip", remote=remote, login=remote, digest=True)
                self.assertEqual(status, 200)
                self.assertEqual(body, {key: self.manifest[key] for key in ("size", "sha256")})
                self.assertEqual(headers["Content-Type"], "application/zip")
                self.assertEqual(headers["Content-Length"], str(self.manifest["size"]))
                self.assertEqual(headers["Content-Disposition"], f'attachment; filename="{FILENAME}"')
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(headers["Cache-Control"], "private, no-store")

    def test_public_download_and_metadata_require_login(self):
        status, headers, _ = self.request("/downloads/latest.zip", remote=True)
        self.assertEqual((status, headers.get("Location")), (302, "/login?download=1"))
        self.assertEqual(self.request("/api/releases/latest", remote=True)[0], 401)
        status, _, payload = self.request("/api/releases/latest", remote=True, login=True)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload), {**self.manifest, "url": "/downloads/latest.zip"})

    def test_sensitive_files_and_arbitrary_download_paths_are_not_exposed(self):
        for path in ("/.env", "/.tavern/releases/latest.json", "/downloads/latest.json", "/downloads/" + FILENAME,
                     "/downloads/../.env", "/downloads/%2e%2e/.env", "/downloads/latest.zip/.env"):
            for remote in (False, True):
                with self.subTest(path=path, remote=remote):
                    self.assertIn(self.request(path, remote=remote, login=remote)[0], (400, 404))

    def test_missing_manifest_returns_clear_404_without_breaking_startup(self):
        manifest = self.directory / "latest.json"
        raw = manifest.read_bytes()
        try:
            manifest.unlink()
            for path in ("/downloads/latest.zip", "/api/releases/latest"):
                status, _, payload = self.request(path)
                self.assertEqual(status, 404)
                self.assertIn("下载包暂未准备好", json.loads(payload)["error"])
            self.assertEqual(self.request("/api/health")[0], 200)
        finally:
            manifest.write_bytes(raw)

    def test_default_release_directory_does_not_follow_chat_data_directory(self):
        with patch("app.Releases") as factory:
            server = create_server(0, data_dir=self.root / "separate-data", gateway=FakeGateway())
            try:
                from app import ROOT
                factory.assert_called_once_with(ROOT / ".tavern" / "releases")
            finally:
                server.server_close()


if __name__ == "__main__":
    unittest.main()
