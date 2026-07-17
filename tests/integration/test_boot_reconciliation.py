"""
Boot reconciliation integration tests.

Simulates daemon starting before the network is ready (the real boot-time
race condition) and asserts that the startup reconciliation window still
drives the system to CONNECTED without any manual commands.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from captivity.core.login import LoginResult
from captivity.core.probe import ConnectivityStatus
from captivity.core.state import ConnectionState
from captivity.daemon.network_monitor import NetworkEvent
from captivity.daemon.runner import (
    DaemonRunner,
    STARTUP_RECONCILIATION_WINDOW,
    STARTUP_RECONCILIATION_INTERVAL,
)


def _make_probe(status: ConnectivityStatus) -> MagicMock:
    m = MagicMock()
    m.status = status
    m.detection_method = "test"
    m.probe_details = []
    m.has_captcha = False
    m.confidence = 1.0
    m.has_captive_portal = status == ConnectivityStatus.PORTAL_DETECTED
    return m


class TestStartupReconciliationWindow(unittest.TestCase):
    """Daemon must probe aggressively during the startup window even if no NM events arrive."""

    def test_constants_are_sane(self):
        self.assertGreater(STARTUP_RECONCILIATION_WINDOW, 0)
        self.assertGreater(STARTUP_RECONCILIATION_INTERVAL, 0)
        self.assertLess(STARTUP_RECONCILIATION_INTERVAL, STARTUP_RECONCILIATION_WINDOW)

    def test_in_startup_window_true_at_start(self):
        runner = DaemonRunner()
        self.assertTrue(runner._in_startup_window())

    def test_in_startup_window_false_after_window(self):
        runner = DaemonRunner()
        runner._startup_time = time.time() - STARTUP_RECONCILIATION_WINDOW - 1
        self.assertFalse(runner._in_startup_window())

    def test_startup_probe_due_immediately(self):
        """First probe is always due (last_startup_probe == 0)."""
        runner = DaemonRunner()
        self.assertTrue(runner._startup_reconciliation_due())

    def test_startup_probe_not_due_too_soon(self):
        runner = DaemonRunner()
        runner._last_startup_probe = time.time()  # just ran
        self.assertFalse(runner._startup_reconciliation_due())

    def test_startup_probe_due_after_interval(self):
        runner = DaemonRunner()
        runner._last_startup_probe = time.time() - STARTUP_RECONCILIATION_INTERVAL - 1
        self.assertTrue(runner._startup_reconciliation_due())

    def test_startup_probe_not_due_after_window_expires(self):
        runner = DaemonRunner()
        runner._startup_time = time.time() - STARTUP_RECONCILIATION_WINDOW - 1
        runner._last_startup_probe = time.time() - STARTUP_RECONCILIATION_INTERVAL - 10
        self.assertFalse(runner._startup_reconciliation_due())


class TestBootLateWiFiConvergence(unittest.TestCase):
    """
    Boot scenario: daemon starts before WiFi is associated.

    Timeline:
      t=0   daemon starts, first probe → NETWORK_UNAVAILABLE
      t=5   startup reconciliation probe → NETWORK_UNAVAILABLE (WiFi still not up)
      t=10  startup reconciliation probe → PORTAL_DETECTED   (WiFi associated, portal active)
      →     login succeeds
      →     state == CONNECTED
    """

    @patch("captivity.daemon.runner.probe_connectivity_detailed")
    @patch("captivity.daemon.runner.do_login")
    @patch("captivity.daemon.network_monitor.get_active_wifi_ssid")
    def test_late_wifi_convergence(self, mock_ssid, mock_login, mock_probe):
        mock_ssid.return_value = "T-VIT"
        mock_login.return_value = LoginResult.SUCCESS

        # Probe sequence: no network → no network → portal → (CONNECTED via login)
        mock_probe.side_effect = [
            _make_probe(ConnectivityStatus.NETWORK_UNAVAILABLE),
            _make_probe(ConnectivityStatus.NETWORK_UNAVAILABLE),
            _make_probe(ConnectivityStatus.PORTAL_DETECTED),
        ]

        runner = DaemonRunner(network=None, portal_url=None)
        runner.state_machine.debounce_duration = 0.0

        # Simulate t=0: initial probe on startup
        runner._run_probe()
        self.assertEqual(runner.state_machine.state, ConnectionState.ERROR)

        # Simulate t=5: startup reconciliation probe (WiFi still not up)
        runner._run_probe()
        self.assertEqual(runner.state_machine.state, ConnectionState.ERROR)

        # Simulate t=10: startup reconciliation probe (WiFi now associated, portal active)
        runner._run_probe()
        # login() was called and succeeded → CONNECTED
        self.assertEqual(runner.state_machine.state, ConnectionState.CONNECTED)
        mock_login.assert_called_once()

    @patch("captivity.daemon.runner.probe_connectivity_detailed")
    @patch("captivity.daemon.runner.do_login")
    @patch("captivity.daemon.network_monitor.get_active_wifi_ssid")
    def test_connected_directly_no_portal(self, mock_ssid, mock_login, mock_probe):
        """Happy path: network already connected at boot → CONNECTED immediately."""
        mock_ssid.return_value = "T-VIT"
        mock_probe.return_value = _make_probe(ConnectivityStatus.CONNECTED)

        runner = DaemonRunner(network=None, portal_url=None)
        runner.state_machine.debounce_duration = 0.0

        runner._run_probe()

        self.assertEqual(runner.state_machine.state, ConnectionState.CONNECTED)
        mock_login.assert_not_called()


class TestNoManualCommandsRequired(unittest.TestCase):
    """Assert that the daemon reaches CONNECTED purely through autonomous reconciliation."""

    @patch("captivity.daemon.runner.probe_connectivity_detailed")
    @patch("captivity.daemon.runner.do_login")
    @patch("captivity.daemon.network_monitor.get_active_wifi_ssid")
    def test_no_network_arg_no_event_still_converges(
        self, mock_ssid, mock_login, mock_probe
    ):
        """
        Daemon initialised with no --network and receives no NM events.
        Startup reconciliation eventually finds the portal and logs in.
        """
        mock_ssid.return_value = "T-VIT"
        mock_login.return_value = LoginResult.SUCCESS
        mock_probe.return_value = _make_probe(ConnectivityStatus.PORTAL_DETECTED)

        runner = DaemonRunner(network=None, portal_url=None)
        runner.state_machine.debounce_duration = 0.0

        # Simulate what the reconciliation window does without events
        runner._run_probe()

        self.assertEqual(runner.state_machine.state, ConnectionState.CONNECTED)
        self.assertEqual(runner.network, "T-VIT")  # SSID was auto-detected

    @patch("captivity.daemon.runner.probe_connectivity_detailed")
    @patch("captivity.daemon.runner.do_login")
    @patch("captivity.daemon.network_monitor.get_active_wifi_ssid")
    def test_nm_event_followed_by_reconciliation(
        self, mock_ssid, mock_login, mock_probe
    ):
        """NM sends CONNECTED event → probe confirms PORTAL → login → CONNECTED."""
        mock_ssid.return_value = "T-VIT"
        mock_login.return_value = LoginResult.SUCCESS
        mock_probe.return_value = _make_probe(ConnectivityStatus.PORTAL_DETECTED)

        runner = DaemonRunner(network=None, portal_url=None)
        runner.state_machine.debounce_duration = 0.0

        runner._handle_network_event(NetworkEvent.CONNECTED)

        self.assertEqual(runner.state_machine.state, ConnectionState.CONNECTED)
        mock_login.assert_called_once()


if __name__ == "__main__":
    unittest.main()
