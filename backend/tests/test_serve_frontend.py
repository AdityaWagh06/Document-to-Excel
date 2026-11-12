"""SERVE_FRONTEND=true: the backend serves the built web app (no-Docker setup)."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.app import create_app
from backend.app.config.settings import settings


class TestServeFrontend(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        dist = Path(self.tmp.name) / "dist"
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
        (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
        (dist / "logo.svg").write_text("<svg/>", encoding="utf-8")
        (Path(self.tmp.name) / "secret.txt").write_text("secret", encoding="utf-8")
        patches = [
            mock.patch.object(settings, "serve_frontend", True),
            mock.patch.object(settings, "frontend_dist_dir", dist),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.client = create_app().test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def get(self, path, client=None):
        resp = (client or self.client).get(path)
        data, status = resp.get_data(), resp.status_code
        resp.close()  # release the file handle (Windows cannot delete open files)
        return status, data

    def test_index_and_assets_are_public(self):
        status, data = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(b'id="root"', data)
        self.assertEqual(self.get("/assets/app.js")[0], 200)
        self.assertEqual(self.get("/logo.svg")[0], 200)

    def test_api_still_requires_login(self):
        self.assertEqual(self.get("/api/v1/documents")[0], 401)
        self.assertEqual(self.get("/api/v1/health")[0], 200)

    def test_no_path_traversal(self):
        for path in ("/assets/../../secret.txt", "/assets/%2e%2e/%2e%2e/secret.txt", "/assets/..%5c..%5csecret.txt"):
            status, data = self.get(path)
            self.assertNotEqual(data, b"secret", path)
            self.assertIn(status, (401, 404), path)

    def test_disabled_by_default(self):
        with mock.patch.object(settings, "serve_frontend", False):
            client = create_app().test_client()
        self.assertNotIn(b'id="root"', self.get("/", client)[1])


if __name__ == "__main__":
    unittest.main()
