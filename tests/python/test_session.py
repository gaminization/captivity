"""Tests for captivity.telemetry.session module."""

import time
import unittest

from captivity.telemetry.session import Session, SessionTracker


class TestSession(unittest.TestCase):
    """Test Session class."""

    def test_create(self):
        s = Session("TestNet", plugin="pronto")
        self.assertEqual(s.network, "TestNet")
        self.assertEqual(s.plugin, "pronto")
        self.assertTrue(s.is_active)

    def test_duration_active(self):
        s = Session("Net")
        s.start_time = time.time() - 120  # 2 minutes ago
        self.assertGreater(s.duration, 119)

    def test_duration_ended(self):
        s = Session("Net")
        s.start_time = 1000.0
        s.end_time = 1060.0
        self.assertAlmostEqual(s.duration, 60.0)

    def test_end(self):
        s = Session("Net")
        self.assertTrue(s.is_active)
        s.end()
        self.assertFalse(s.is_active)
        self.assertIsNotNone(s.end_time)

    def test_end_idempotent(self):
        s = Session("Net")
        s.end()
        end1 = s.end_time
        s.end()
        self.assertEqual(s.end_time, end1)

    def test_duration_str_seconds(self):
        s = Session("Net")
        s.start_time = 1000.0
        s.end_time = 1045.0
        self.assertEqual(s.duration_str, "45s")

    def test_duration_str_minutes(self):
        s = Session("Net")
        s.start_time = 1000.0
        s.end_time = 1125.0
        self.assertIn("m", s.duration_str)

    def test_duration_str_hours(self):
        s = Session("Net")
        s.start_time = 1000.0
        s.end_time = 5600.0
        self.assertIn("h", s.duration_str)

    def test_to_dict_from_dict(self):
        s = Session("Net", plugin="generic")
        s.end()
        data = s.to_dict()
        s2 = Session.from_dict(data)
        self.assertEqual(s.network, s2.network)
        self.assertEqual(s.plugin, s2.plugin)
        self.assertAlmostEqual(s.duration, s2.duration, places=1)

    def test_repr(self):
        s = Session("Net")
        self.assertIn("Net", repr(s))
        self.assertIn("active", repr(s))


class TestSessionTracker(unittest.TestCase):
    """Test SessionTracker class."""

    def test_start(self):
        t = SessionTracker()
        s = t.start("Net")
        self.assertEqual(s.network, "Net")
        self.assertIsNotNone(t.current)

    def test_start_ends_previous(self):
        t = SessionTracker()
        t.start("Net1")
        t.start("Net2")
        self.assertEqual(t.current.network, "Net2")
        self.assertEqual(len(t.history), 1)

    def test_end(self):
        t = SessionTracker()
        t.start("Net")
        ended = t.end()
        self.assertIsNotNone(ended)
        self.assertIsNone(t.current)

    def test_end_no_session(self):
        t = SessionTracker()
        self.assertIsNone(t.end())

    def test_session_count(self):
        t = SessionTracker()
        self.assertEqual(t.session_count, 0)
        t.start("Net1")
        self.assertEqual(t.session_count, 1)
        t.start("Net2")
        self.assertEqual(t.session_count, 2)  # 1 history + 1 current

    def test_total_uptime(self):
        t = SessionTracker()
        s = t.start("Net")
        s.start_time = time.time() - 60
        self.assertGreater(t.total_uptime, 59)

    def test_max_history(self):
        t = SessionTracker(max_history=3)
        for i in range(5):
            t.start(f"Net{i}")
        t.end()
        self.assertLessEqual(len(t.history), 3)


if __name__ == "__main__":
    unittest.main()
