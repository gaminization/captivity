"""Tests for the dashboard server and API."""

import json
import time
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import unittest

from captivity.dashboard.server import DashboardServer


class TestDashboardServer(unittest.TestCase):
    def setUp(self):
        self.port = 8789
        self.server = DashboardServer(port=self.port, password="secret")
        self.server.start(blocking=False)
        time.sleep(0.1)  # Allow server to start

    def tearDown(self):
        self.server.stop()
        time.sleep(0.1)

    def test_unauthorized_access(self):
        """Without token, API should return 401."""
        req = Request(f"http://127.0.0.1:{self.port}/api/status")
        with self.assertRaises(HTTPError) as cm:
            urlopen(req)
        self.assertEqual(cm.exception.code, 401)

    def test_authorized_access_header(self):
        """With correct Bearer token, API should return 200."""
        req = Request(f"http://127.0.0.1:{self.port}/api/status")
        req.add_header("Authorization", "Bearer secret")
        resp = urlopen(req)
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.read().decode())
        self.assertIn("state", data)

    def test_authorized_access_query(self):
        """With correct query token, page should load."""
        req = Request(f"http://127.0.0.1:{self.port}/?token=secret")
        resp = urlopen(req)
        self.assertEqual(resp.status, 200)
        self.assertIn(b"Captivity Dashboard", resp.read())

    def test_manifest_json(self):
        """Manifest should be served with correct content type and bypass auth."""
        req = Request(f"http://127.0.0.1:{self.port}/manifest.json")
        resp = urlopen(req)
        self.assertEqual(resp.status, 200)
        self.assertEqual(
            resp.getheader("Content-Type"), "application/manifest+json; charset=utf-8"
        )
        self.assertIn(b"standalone", resp.read())

    def test_service_worker_js(self):
        """Service worker should be served with correct content type and bypass auth."""
        req = Request(f"http://127.0.0.1:{self.port}/sw.js")
        resp = urlopen(req)
        self.assertEqual(resp.status, 200)
        self.assertEqual(
            resp.getheader("Content-Type"), "application/javascript; charset=utf-8"
        )
        self.assertIn(b"addEventListener", resp.read())


if __name__ == "__main__":
    unittest.main()
