"""Tests for captivity.telemetry.stats module."""

import json
import tempfile
import unittest
from pathlib import Path

from captivity.telemetry.stats import (
    ConnectionEvent,
    NetworkStats,
    StatsDatabase,
)


class TestConnectionEvent(unittest.TestCase):
    """Test ConnectionEvent class."""

    def test_create(self):
        e = ConnectionEvent("login_success", "TestNet")
        self.assertEqual(e.event_type, "login_success")
        self.assertGreater(e.timestamp, 0)

    def test_to_dict_from_dict(self):
        e = ConnectionEvent("login_failure", "Net", "timeout")
        data = e.to_dict()
        e2 = ConnectionEvent.from_dict(data)
        self.assertEqual(e.event_type, e2.event_type)
        self.assertEqual(e.details, e2.details)


class TestNetworkStats(unittest.TestCase):
    """Test NetworkStats class."""

    def test_success_rate_no_logins(self):
        ns = NetworkStats("Net")
        self.assertEqual(ns.success_rate, 0.0)

    def test_success_rate(self):
        ns = NetworkStats("Net")
        ns.login_successes = 8
        ns.login_failures = 2
        self.assertAlmostEqual(ns.success_rate, 0.8)

    def test_to_dict_from_dict(self):
        ns = NetworkStats("Net")
        ns.login_successes = 5
        ns.total_uptime = 3600.0
        data = ns.to_dict()
        ns2 = NetworkStats.from_dict(data)
        self.assertEqual(ns.login_successes, ns2.login_successes)
        self.assertEqual(ns.total_uptime, ns2.total_uptime)


class TestStatsDatabase(unittest.TestCase):
    """Test StatsDatabase class."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_file = Path(self.tmpdir) / "stats.json"
        self.db = StatsDatabase(stats_file=self.db_file)

    def test_empty(self):
        self.assertEqual(self.db.total_logins, 0)
        self.assertEqual(self.db.total_uptime, 0.0)

    def test_record_login_success(self):
        self.db.record_login_success("CoffeeWifi")
        ns = self.db.get_network_stats("CoffeeWifi")
        self.assertEqual(ns.login_successes, 1)

    def test_record_login_failure(self):
        self.db.record_login_failure("CoffeeWifi", "timeout")
        ns = self.db.get_network_stats("CoffeeWifi")
        self.assertEqual(ns.login_failures, 1)

    def test_record_session_end(self):
        self.db.record_session_end("Net", 3600.0, rx_bytes=1000000, tx_bytes=500000)
        ns = self.db.get_network_stats("Net")
        self.assertAlmostEqual(ns.total_uptime, 3600.0)
        self.assertEqual(ns.total_rx_bytes, 1000000)

    def test_record_reconnect(self):
        self.db.record_reconnect("Net")
        ns = self.db.get_network_stats("Net")
        self.assertEqual(ns.reconnect_count, 1)

    def test_get_all_stats(self):
        self.db.record_login_success("Net1")
        self.db.record_login_success("Net2")
        stats = self.db.get_all_stats()
        self.assertEqual(len(stats), 2)

    def test_get_history(self):
        self.db.record_login_success("Net")
        self.db.record_login_failure("Net")
        history = self.db.get_history(limit=10)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].event_type, "login_failure")  # newest first

    def test_total_logins(self):
        self.db.record_login_success("Net1")
        self.db.record_login_success("Net2")
        self.db.record_login_success("Net1")
        self.assertEqual(self.db.total_logins, 3)

    def test_total_bandwidth(self):
        self.db.record_session_end("Net", 100, rx_bytes=1000, tx_bytes=500)
        self.assertEqual(self.db.total_bandwidth, 1500)

    def test_persistence(self):
        self.db.record_login_success("Net")
        db2 = StatsDatabase(stats_file=self.db_file)
        self.assertEqual(db2.total_logins, 1)

    def test_handles_corrupt_file(self):
        with open(self.db_file, "w") as f:
            f.write("not json")
        db = StatsDatabase(stats_file=self.db_file)
        self.assertEqual(db.total_logins, 0)


if __name__ == "__main__":
    unittest.main()
