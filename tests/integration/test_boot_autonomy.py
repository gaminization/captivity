"""Integration tests for daemon boot autonomy."""

import unittest
from unittest.mock import patch, MagicMock

from captivity.core.probe import ConnectivityStatus
from captivity.core.state import ConnectionState
from captivity.daemon.runner import DaemonRunner
from captivity.daemon.network_monitor import NetworkEvent
from captivity.core.login import LoginResult


class TestBootAutonomy(unittest.TestCase):
    """Test the full autonomous boot flow without manual intervention."""

    @patch("captivity.daemon.runner.probe_connectivity_detailed")
    @patch("captivity.daemon.runner.do_login")
    @patch("captivity.daemon.network_monitor.get_active_wifi_ssid")
    def test_boot_autonomy_flow(self, mock_get_ssid, mock_login, mock_probe):
        """Simulate the boot flow matching the autonomy requirements."""

        # Setup mocks
        mock_get_ssid.return_value = "T-VIT"

        # First probe: Portal detected
        probe_portal = MagicMock()
        probe_portal.status = ConnectivityStatus.PORTAL_DETECTED
        probe_portal.detection_method = "http_redirect"
        probe_portal.probe_details = ["Found portal at http://phc..."]

        # Second probe (after login): Connected (HTTP 204 verified)
        probe_connected = MagicMock()
        probe_connected.status = ConnectivityStatus.CONNECTED
        probe_connected.detection_method = "http204"
        probe_connected.probe_details = ["Google 204 ok"]

        # Mock probe responses in sequence
        mock_probe.side_effect = [probe_portal, probe_connected]

        # Mock login success
        mock_login.return_value = LoginResult.SUCCESS

        # Initialize the daemon without hardcoded network (autonomy invariant)
        runner = DaemonRunner(network=None, portal_url=None)
        runner.state_machine.debounce_duration = 0.0

        # Initial state should be INIT
        self.assertEqual(runner.state_machine.state, ConnectionState.INIT)

        # 1. Simulate NetworkManager reconnecting WiFi
        # The daemon receives a CONNECTED event from the network monitor
        runner._handle_network_event(NetworkEvent.CONNECTED)

        # 2. Daemon should execute _run_probe
        # Probe returns PORTAL, which triggers _handle_portal
        # _handle_portal fetches active SSID ("T-VIT")
        # _handle_portal attempts login, which succeeds
        # _handle_portal sets state to CONNECTED

        self.assertEqual(runner.state_machine.state, ConnectionState.CONNECTED)
        self.assertEqual(runner.network, "T-VIT")

        # Verify no manual CLI flags were required
        mock_get_ssid.assert_called_once()
        mock_login.assert_called_once_with(
            network="T-VIT", portal_url=None, open_browser=True
        )


if __name__ == "__main__":
    unittest.main()
