"""Tests for the event-driven DaemonRunner."""

import unittest
from unittest.mock import patch, MagicMock

from captivity.daemon.runner import DaemonRunner
from captivity.core.state import ConnectionState
from captivity.core.probe import ConnectivityStatus
from captivity.daemon.network_monitor import NetworkEvent
from captivity.core.login import LoginResult


class TestDaemonRunner(unittest.TestCase):
    @patch("captivity.daemon.runner.NetworkMonitor")
    def setUp(self, mock_monitor):
        self.runner = DaemonRunner()
        self.runner.monitor = mock_monitor.return_value
        self.runner.state_machine.debounce_duration = 0.0

    @patch("captivity.daemon.runner.probe_connectivity_detailed")
    def test_run_probe_connected(self, mock_probe):
        mock_result = MagicMock()
        mock_result.status = ConnectivityStatus.CONNECTED
        mock_result.detection_method = "test"
        mock_probe.return_value = mock_result

        self.runner._run_probe()
        self.assertEqual(self.runner.state_machine.state, ConnectionState.CONNECTED)

    @patch("captivity.daemon.runner.probe_connectivity_detailed")
    @patch("captivity.daemon.runner.do_login")
    def test_run_probe_portal_wait_user(self, mock_login, mock_probe):
        mock_result = MagicMock()
        mock_result.status = ConnectivityStatus.PORTAL_DETECTED
        mock_result.detection_method = "test"
        mock_probe.return_value = mock_result

        mock_login.return_value = LoginResult.WAIT_USER
        self.runner.network = "test_net"

        self.runner._run_probe()
        self.assertEqual(self.runner.state_machine.state, ConnectionState.WAIT_USER)

    @patch("captivity.daemon.runner.probe_connectivity_detailed")
    @patch("captivity.daemon.runner.do_login")
    def test_run_probe_portal_success(self, mock_login, mock_probe):
        mock_result = MagicMock()
        mock_result.status = ConnectivityStatus.PORTAL_DETECTED
        mock_result.detection_method = "test"
        mock_probe.return_value = mock_result

        mock_login.return_value = LoginResult.SUCCESS
        self.runner.network = "test_net"

        self.runner._run_probe()
        self.assertEqual(self.runner.state_machine.state, ConnectionState.CONNECTED)

    def test_handle_network_event_disconnected(self):
        self.runner._handle_network_event(NetworkEvent.DISCONNECTED)
        self.assertEqual(self.runner.state_machine.state, ConnectionState.ERROR)

    @patch("captivity.daemon.runner.DaemonRunner._run_probe")
    def test_handle_network_event_connected(self, mock_run_probe):
        self.runner._handle_network_event(NetworkEvent.CONNECTED)
        mock_run_probe.assert_called_once()

    def test_adaptive_cooldown(self):
        # 1st call -> True
        self.assertTrue(self.runner._should_open_browser())
        # 2nd call immediate -> False
        self.assertFalse(self.runner._should_open_browser())

        # Fast forward 61s -> True
        with patch(
            "captivity.daemon.runner.time.time",
            return_value=self.runner.last_browser_open_time + 61,
        ):
            self.assertTrue(self.runner._should_open_browser())

    def test_fault_tracker_exponential_backoff(self):
        from captivity.daemon.runner import FaultTracker

        tracker = FaultTracker(max_crashes_per_window=3)

        # 1st crash: base delay
        delay1 = tracker.record_crash()
        self.assertEqual(delay1, 5.0)

        # 2nd crash: double
        delay2 = tracker.record_crash()
        self.assertEqual(delay2, 10.0)

        # 3rd crash: double again
        delay3 = tracker.record_crash()
        self.assertEqual(delay3, 20.0)

        # 4th crash: fatal (exceeds 3)
        with self.assertRaises(SystemExit):
            tracker.record_crash()


if __name__ == "__main__":
    unittest.main()
