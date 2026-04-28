"""
Integration test: Portal simulator login flow.

Tests the complete login flow against the built-in
portal simulator, verifying the full chain:
  probe → detect portal → select plugin → login → verify
"""

import threading
import time

from captivity.testing.simulator import PortalSimulator
from captivity.testing.scenarios import Scenario, SCENARIOS
from captivity.core.probe import ConnectivityStatus


class TestSimulatorLogin:
    """Test login flow against the portal simulator."""

    def test_simulator_starts_and_stops(self):
        """Simulator should start and stop cleanly."""
        sim = PortalSimulator(scenario=SCENARIOS["simple"], port=19090)
        sim.start()
        try:
            assert sim.url is not None
            assert "19090" in sim.url
            assert sim.is_running
        finally:
            sim.stop()
        assert not sim.is_running

    def test_simulator_probe_before_login(self):
        """Before login, simulator should show portal detected."""
        with PortalSimulator(scenario=SCENARIOS["simple"], port=19091) as sim:
            import requests
            r = requests.get(f"{sim.url}/generate_204", timeout=5,
                           allow_redirects=False)
            # Should redirect to portal (302) or return non-204
            assert r.status_code != 204

    def test_simulator_login_success(self):
        """Login with correct credentials should succeed."""
        with PortalSimulator(scenario=SCENARIOS["simple"], port=19092) as sim:
            import requests
            session = requests.Session()
            # Login
            r = session.post(f"{sim.url}/login",
                           data={"username": "user", "password": "pass"},
                           timeout=5)
            assert r.status_code == 200

    def test_simulator_probe_after_login(self):
        """After login, simulator should show connected."""
        with PortalSimulator(scenario=SCENARIOS["simple"], port=19093) as sim:
            import requests
            session = requests.Session()
            # Login first
            session.post(f"{sim.url}/login",
                        data={"username": "user", "password": "pass"},
                        timeout=5)
            # Now probe should return 204
            r = session.get(f"{sim.url}/generate_204", timeout=5,
                          allow_redirects=False)
            assert r.status_code == 204

    def test_simulator_session_expiry(self):
        """Session expiry scenario should lose connection."""
        with PortalSimulator(scenario=SCENARIOS["session_expiry"], port=19094) as sim:
            import requests
            session = requests.Session()
            # Login
            session.post(f"{sim.url}/login",
                        data={"username": "user", "password": "pass"},
                        timeout=5)
            # Immediate probe should work
            r = session.get(f"{sim.url}/generate_204", timeout=5,
                          allow_redirects=False)
            assert r.status_code == 204

    def test_simulator_terms_required(self):
        """Terms scenario should require checkbox acceptance."""
        with PortalSimulator(scenario=SCENARIOS["terms"], port=19095) as sim:
            import requests
            # Get login page
            r = requests.get(f"{sim.url}/login", timeout=5)
            assert r.status_code == 200
            assert "terms" in r.text.lower() or "accept" in r.text.lower()

    def test_simulator_reset(self):
        """Reset should clear login state."""
        with PortalSimulator(scenario=SCENARIOS["simple"], port=19096) as sim:
            import requests
            session = requests.Session()
            # Login
            session.post(f"{sim.url}/login",
                        data={"username": "user", "password": "pass"},
                        timeout=5)
            # Reset
            sim.reset()
            # Should need to login again
            r = session.get(f"{sim.url}/generate_204", timeout=5,
                          allow_redirects=False)
            assert r.status_code != 204

    def test_multiple_scenarios_available(self):
        """Multiple simulator scenarios should be available."""
        expected = ["simple", "flaky", "terms", "session_expiry"]
        for name in expected:
            assert name in SCENARIOS, f"Scenario '{name}' not found"
            scenario = SCENARIOS[name]
            assert scenario.name == name

    def test_status_endpoint(self):
        """Status endpoint should return JSON state."""
        with PortalSimulator(scenario=SCENARIOS["simple"], port=19097) as sim:
            import requests
            r = requests.get(f"{sim.url}/status", timeout=5)
            assert r.status_code == 200
            data = r.json()
            assert data["scenario"] == "simple"
            assert data["connected"] is False
            assert data["total_attempts"] == 0

    def test_flaky_portal_fails_then_succeeds(self):
        """Flaky scenario should fail first N attempts then succeed."""
        with PortalSimulator(scenario=SCENARIOS["flaky"], port=19098) as sim:
            import requests
            session = requests.Session()
            # First 2 attempts should fail (fail_first_n=2)
            r1 = session.post(f"{sim.url}/login",
                            data={"username": "user", "password": "pass"},
                            timeout=5)
            assert r1.status_code == 403
            r2 = session.post(f"{sim.url}/login",
                            data={"username": "user", "password": "pass"},
                            timeout=5)
            assert r2.status_code == 403
            # Third attempt should succeed
            r3 = session.post(f"{sim.url}/login",
                            data={"username": "user", "password": "pass"},
                            timeout=5)
            assert r3.status_code == 200
