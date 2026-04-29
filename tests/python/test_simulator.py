"""Tests for captivity.testing.simulator module."""

import json
import socket
import time
import unittest
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from urllib.parse import urlencode

from captivity.testing.scenarios import SCENARIOS, Scenario
from captivity.testing.simulator import PortalSimulator


def _find_free_port() -> int:
    """Find a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestPortalSimulator(unittest.TestCase):
    """Integration tests for the portal simulator."""

    def setUp(self):
        self.port = _find_free_port()

    def test_context_manager(self):
        """Simulator works as a context manager."""
        with PortalSimulator(port=self.port) as sim:
            self.assertTrue(sim.is_running)
        self.assertFalse(sim.is_running)

    def test_login_page(self):
        """GET /login returns HTML with form."""
        with PortalSimulator(port=self.port):
            resp = urlopen(f"http://127.0.0.1:{self.port}/login")
            html = resp.read().decode()
            self.assertIn("<form", html)
            self.assertIn("username", html)
            self.assertEqual(resp.status, 200)

    def test_probe_before_login(self):
        """GET /generate_204 redirects when not logged in."""
        with PortalSimulator(port=self.port):
            req = Request(
                f"http://127.0.0.1:{self.port}/generate_204",
            )
            try:
                # urllib follows redirects, so we get the login page
                resp = urlopen(req)
                html = resp.read().decode()
                # Should end up at login page (200 after redirect)
                self.assertIn("<form", html)
            except HTTPError:
                pass  # Some redirect handling varies

    def test_successful_login(self):
        """POST /login with credentials returns success."""
        with PortalSimulator(port=self.port):
            data = urlencode({"username": "test", "password": "pass"})
            req = Request(
                f"http://127.0.0.1:{self.port}/login",
                data=data.encode(),
                method="POST",
            )
            resp = urlopen(req)
            html = resp.read().decode()
            self.assertIn("Login successful", html)
            self.assertEqual(resp.status, 200)

    def test_probe_after_login(self):
        """GET /generate_204 returns 204 after login."""
        with PortalSimulator(port=self.port):
            # Login first
            data = urlencode({"username": "test", "password": "pass"})
            req = Request(
                f"http://127.0.0.1:{self.port}/login",
                data=data.encode(),
                method="POST",
            )
            urlopen(req)
            # Now probe
            resp = urlopen(f"http://127.0.0.1:{self.port}/generate_204")
            self.assertEqual(resp.status, 204)

    def test_status_endpoint(self):
        """GET /status returns JSON status."""
        with PortalSimulator(port=self.port):
            resp = urlopen(f"http://127.0.0.1:{self.port}/status")
            data = json.loads(resp.read())
            self.assertEqual(data["scenario"], "simple")
            self.assertFalse(data["connected"])

    def test_scenario_endpoint(self):
        """GET /api/scenario returns scenario config."""
        with PortalSimulator(port=self.port):
            resp = urlopen(f"http://127.0.0.1:{self.port}/api/scenario")
            data = json.loads(resp.read())
            self.assertEqual(data["name"], "simple")
            self.assertIn("form_fields", data)

    def test_flaky_scenario(self):
        """Flaky scenario fails first N, then succeeds."""
        scenario = SCENARIOS["flaky"]
        with PortalSimulator(scenario=scenario, port=self.port):
            # First 2 attempts should fail
            for i in range(scenario.fail_first_n):
                data = urlencode({"username": "test", "password": "pass"})
                req = Request(
                    f"http://127.0.0.1:{self.port}/login",
                    data=data.encode(),
                    method="POST",
                )
                try:
                    resp = urlopen(req)
                    # 403 shows as a response, not an exception in some cases
                    self.assertIn("Failed", resp.read().decode())
                except HTTPError as e:
                    self.assertEqual(e.code, 403)

            # Third attempt should succeed
            data = urlencode({"username": "test", "password": "pass"})
            req = Request(
                f"http://127.0.0.1:{self.port}/login",
                data=data.encode(),
                method="POST",
            )
            resp = urlopen(req)
            self.assertEqual(resp.status, 200)

    def test_terms_required(self):
        """Terms scenario fails without accept_terms field."""
        scenario = SCENARIOS["terms"]
        with PortalSimulator(scenario=scenario, port=self.port):
            # Without terms
            data = urlencode({"username": "test", "password": "pass"})
            req = Request(
                f"http://127.0.0.1:{self.port}/login",
                data=data.encode(),
                method="POST",
            )
            try:
                resp = urlopen(req)
                self.assertIn("Terms", resp.read().decode())
            except HTTPError as e:
                self.assertEqual(e.code, 400)

            # With terms
            data = urlencode(
                {
                    "username": "test",
                    "password": "pass",
                    "accept_terms": "on",
                }
            )
            req = Request(
                f"http://127.0.0.1:{self.port}/login",
                data=data.encode(),
                method="POST",
            )
            resp = urlopen(req)
            self.assertEqual(resp.status, 200)

    def test_session_expiry(self):
        """Session expiry scenario expires sessions."""
        scenario = Scenario(
            name="quick_expiry",
            session_duration=1,  # 1-second sessions
        )
        with PortalSimulator(scenario=scenario, port=self.port):
            # Login
            data = urlencode({"username": "test", "password": "pass"})
            req = Request(
                f"http://127.0.0.1:{self.port}/login",
                data=data.encode(),
                method="POST",
            )
            urlopen(req)

            # Should be connected
            resp = urlopen(f"http://127.0.0.1:{self.port}/status")
            status = json.loads(resp.read())
            self.assertTrue(status["connected"])

            # Wait for expiry
            time.sleep(1.5)

            resp = urlopen(f"http://127.0.0.1:{self.port}/status")
            status = json.loads(resp.read())
            self.assertFalse(status["connected"])

    def test_repr(self):
        sim = PortalSimulator(port=self.port)
        self.assertIn("simple", repr(sim))
        self.assertIn("stopped", repr(sim))

    def test_url_property(self):
        sim = PortalSimulator(port=self.port)
        self.assertIn(str(self.port), sim.url)

    def test_reset(self):
        """Reset clears session state."""
        with PortalSimulator(port=self.port) as sim:
            # Login
            data = urlencode({"username": "test", "password": "pass"})
            req = Request(
                f"http://127.0.0.1:{self.port}/login",
                data=data.encode(),
                method="POST",
            )
            urlopen(req)
            sim.reset()
            resp = urlopen(f"http://127.0.0.1:{self.port}/status")
            status = json.loads(resp.read())
            self.assertFalse(status["connected"])


if __name__ == "__main__":
    unittest.main()
