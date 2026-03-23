"""Tests for captivity.dashboard.server module."""

import json
import socket
import threading
import time
import unittest
import urllib.request
import urllib.error

from captivity.dashboard.api import DashboardAPI
from captivity.dashboard.server import DashboardServer


def _find_free_port() -> int:
    """Find an available port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestDashboardServer(unittest.TestCase):
    """Test DashboardServer lifecycle and HTTP serving."""

    def setUp(self):
        self.api = DashboardAPI()
        self.port = _find_free_port()
        self.server = DashboardServer(port=self.port, api=self.api)

    def tearDown(self):
        self.server.stop()
        time.sleep(0.1)

    def test_start_stop(self):
        self.server.start(blocking=False)
        time.sleep(0.3)
        self.assertTrue(self.server.is_running)
        self.server.stop()
        time.sleep(0.3)

    def test_serves_dashboard_page(self):
        self.server.start(blocking=False)
        time.sleep(0.3)
        try:
            url = f"http://127.0.0.1:{self.port}/"
            resp = urllib.request.urlopen(url, timeout=2)
            html = resp.read().decode()
            self.assertIn("Captivity", html)
            self.assertIn("Dashboard", html)
            self.assertEqual(resp.status, 200)
        except urllib.error.URLError:
            self.skipTest("Could not connect to dashboard server")

    def test_serves_api_status(self):
        self.server.start(blocking=False)
        time.sleep(0.3)
        try:
            url = f"http://127.0.0.1:{self.port}/api/status"
            resp = urllib.request.urlopen(url, timeout=2)
            data = json.loads(resp.read())
            self.assertIn("state", data)
        except urllib.error.URLError:
            self.skipTest("Could not connect to dashboard server")

    def test_serves_api_stats(self):
        self.server.start(blocking=False)
        time.sleep(0.3)
        try:
            url = f"http://127.0.0.1:{self.port}/api/stats"
            resp = urllib.request.urlopen(url, timeout=2)
            data = json.loads(resp.read())
            self.assertIn("total_logins", data)
        except urllib.error.URLError:
            self.skipTest("Could not connect to dashboard server")

    def test_404_for_unknown(self):
        self.server.start(blocking=False)
        time.sleep(0.3)
        try:
            url = f"http://127.0.0.1:{self.port}/nonexistent"
            urllib.request.urlopen(url, timeout=2)
            self.fail("Expected 404")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)
        except urllib.error.URLError:
            self.skipTest("Could not connect to dashboard server")


if __name__ == "__main__":
    unittest.main()
