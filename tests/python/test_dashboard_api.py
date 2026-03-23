"""Tests for captivity.dashboard.api module."""

import unittest
from unittest.mock import MagicMock

from captivity.dashboard.api import DashboardAPI


class TestDashboardAPIStatus(unittest.TestCase):
    """Test status endpoint."""

    def test_idle_status(self):
        api = DashboardAPI()
        result = api.get_status()
        self.assertEqual(result["state"], "idle")
        self.assertIn("timestamp", result)

    def test_connected_status(self):
        tracker = MagicMock()
        session = MagicMock()
        session.network = "CoffeeWifi"
        session.duration = 300.0
        session.duration_str = "5m 0s"
        tracker.current = session
        api = DashboardAPI(session_tracker=tracker)
        result = api.get_status()
        self.assertEqual(result["state"], "connected")
        self.assertEqual(result["network"], "CoffeeWifi")
        self.assertEqual(result["uptime_str"], "5m 0s")


class TestDashboardAPIStats(unittest.TestCase):
    """Test stats endpoint."""

    def test_empty_stats(self):
        api = DashboardAPI()
        result = api.get_stats()
        self.assertEqual(result["total_logins"], 0)

    def test_with_stats_db(self):
        db = MagicMock()
        db.total_logins = 5
        db.total_uptime = 7200.0
        db.total_bandwidth = 1048576
        ns = MagicMock()
        ns.ssid = "Net"
        ns.login_successes = 5
        ns.login_failures = 1
        ns.success_rate = 0.833
        ns.total_uptime = 7200.0
        ns.total_rx_bytes = 500000
        ns.total_tx_bytes = 548576
        ns.reconnect_count = 2
        db.get_all_stats.return_value = [ns]
        api = DashboardAPI(stats_db=db)
        result = api.get_stats()
        self.assertEqual(result["total_logins"], 5)
        self.assertEqual(len(result["networks"]), 1)
        self.assertEqual(result["networks"][0]["ssid"], "Net")


class TestDashboardAPIHistory(unittest.TestCase):
    """Test history endpoint."""

    def test_empty_history(self):
        api = DashboardAPI()
        result = api.get_history()
        self.assertEqual(result, [])

    def test_with_events(self):
        db = MagicMock()
        event = MagicMock()
        event.timestamp = 1700000000.0
        event.event_type = "login_success"
        event.network = "Net"
        event.details = ""
        db.get_history.return_value = [event]
        api = DashboardAPI(stats_db=db)
        result = api.get_history()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["event_type"], "login_success")


class TestDashboardAPINetworks(unittest.TestCase):
    """Test networks endpoint."""

    def test_empty_networks(self):
        api = DashboardAPI()
        result = api.get_networks()
        self.assertEqual(result, [])

    def test_with_profiles(self):
        db = MagicMock()
        profile = MagicMock()
        profile.ssid = "Net"
        profile.plugin_name = "generic"
        profile.login_count = 3
        profile.has_portal_info = True
        profile.fingerprint.portal_domain = "portal.com"
        profile.fingerprint.gateway_ip = "10.0.0.1"
        db.list_profiles.return_value = [profile]
        api = DashboardAPI(profile_db=db)
        result = api.get_networks()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ssid"], "Net")


class TestDashboardAPIBandwidth(unittest.TestCase):
    """Test bandwidth endpoint."""

    def test_no_monitor(self):
        api = DashboardAPI()
        result = api.get_bandwidth()
        self.assertEqual(result["interface"], "")

    def test_with_monitor(self):
        mon = MagicMock()
        mon.interface = "wlan0"
        usage = MagicMock()
        usage.rx_bytes = 1000
        usage.tx_bytes = 500
        usage.total_bytes = 1500
        mon.get_session_usage.return_value = usage
        mon.get_current_stats.return_value = None
        api = DashboardAPI(bandwidth_monitor=mon)
        result = api.get_bandwidth()
        self.assertEqual(result["interface"], "wlan0")
        self.assertEqual(result["session"]["rx_bytes"], 1000)


class TestDashboardAPIRouting(unittest.TestCase):
    """Test request routing."""

    def test_valid_route(self):
        api = DashboardAPI()
        result = api.handle_request("/api/status")
        self.assertIsNotNone(result)
        self.assertIn("state", result)

    def test_invalid_route(self):
        api = DashboardAPI()
        result = api.handle_request("/api/nonexistent")
        self.assertIsNone(result)

    def test_all_routes_work(self):
        api = DashboardAPI()
        for path in ["/api/status", "/api/stats", "/api/history",
                     "/api/networks", "/api/bandwidth"]:
            result = api.handle_request(path)
            self.assertIsNotNone(result, f"Route {path} returned None")


if __name__ == "__main__":
    unittest.main()
