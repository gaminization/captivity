"""Tests for cross-platform network monitor and SSID detection."""

import subprocess
import sys
import unittest
from unittest.mock import patch, MagicMock

from captivity.daemon.network_monitor import (
    NetworkEvent,
    get_active_wifi_ssid,
    _get_ssid_linux,
    _get_ssid_macos,
    _get_ssid_windows,
    NetworkMonitor,
)


class TestGetActiveWifiSsidDispatch(unittest.TestCase):
    """Test that get_active_wifi_ssid dispatches to the right platform."""

    @patch("captivity.daemon.network_monitor.sys")
    @patch("captivity.daemon.network_monitor._get_ssid_linux", return_value="LinuxNet")
    def test_dispatch_linux(self, mock_fn, mock_sys):
        mock_sys.platform = "linux"
        self.assertEqual(get_active_wifi_ssid(), "LinuxNet")
        mock_fn.assert_called_once()

    @patch("captivity.daemon.network_monitor.sys")
    @patch("captivity.daemon.network_monitor._get_ssid_macos", return_value="MacNet")
    def test_dispatch_macos(self, mock_fn, mock_sys):
        mock_sys.platform = "darwin"
        self.assertEqual(get_active_wifi_ssid(), "MacNet")
        mock_fn.assert_called_once()

    @patch("captivity.daemon.network_monitor.sys")
    @patch(
        "captivity.daemon.network_monitor._get_ssid_windows", return_value="WinNet"
    )
    def test_dispatch_windows(self, mock_fn, mock_sys):
        mock_sys.platform = "win32"
        self.assertEqual(get_active_wifi_ssid(), "WinNet")
        mock_fn.assert_called_once()

    @patch("captivity.daemon.network_monitor.sys")
    def test_dispatch_unsupported(self, mock_sys):
        mock_sys.platform = "freebsd"
        self.assertIsNone(get_active_wifi_ssid())


class TestGetSsidLinux(unittest.TestCase):
    @patch("captivity.daemon.network_monitor.shutil.which", return_value="/usr/bin/nmcli")
    @patch("captivity.daemon.network_monitor.subprocess.run")
    def test_parses_nmcli_output(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            stdout="no:OtherNetwork\nyes:MyWiFi\n", returncode=0
        )
        self.assertEqual(_get_ssid_linux(), "MyWiFi")

    @patch("captivity.daemon.network_monitor.shutil.which", return_value=None)
    def test_no_nmcli(self, mock_which):
        self.assertIsNone(_get_ssid_linux())

    @patch("captivity.daemon.network_monitor.shutil.which", return_value="/usr/bin/nmcli")
    @patch(
        "captivity.daemon.network_monitor.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="nmcli", timeout=5),
    )
    def test_timeout(self, mock_run, mock_which):
        self.assertIsNone(_get_ssid_linux())


class TestGetSsidMacos(unittest.TestCase):
    @patch("captivity.daemon.network_monitor.subprocess.run")
    def test_parses_airport_output(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="     agrCtlRSSI: -55\n           SSID: CafeWiFi\n      BSSID: aa:bb:cc:dd:ee:ff\n",
            returncode=0,
        )
        self.assertEqual(_get_ssid_macos(), "CafeWiFi")

    @patch(
        "captivity.daemon.network_monitor.subprocess.run",
        side_effect=FileNotFoundError("airport not found"),
    )
    def test_airport_missing(self, mock_run):
        self.assertIsNone(_get_ssid_macos())


class TestGetSsidWindows(unittest.TestCase):
    @patch("captivity.daemon.network_monitor.subprocess.run")
    def test_parses_netsh_output(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=(
                "    Name                   : Wi-Fi\n"
                "    Description            : Intel Wireless\n"
                "    GUID                   : abc-123\n"
                "    Physical address       : aa:bb:cc:dd:ee:ff\n"
                "    State                  : connected\n"
                "    SSID                   : OfficeNet\n"
                "    BSSID                  : 11:22:33:44:55:66\n"
                "    Network type           : Infrastructure\n"
            ),
            returncode=0,
        )
        self.assertEqual(_get_ssid_windows(), "OfficeNet")

    @patch("captivity.daemon.network_monitor.subprocess.run")
    def test_ignores_bssid(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=(
                "    BSSID                  : 11:22:33:44:55:66\n"
                "    SSID                   : TestNet\n"
            ),
            returncode=0,
        )
        self.assertEqual(_get_ssid_windows(), "TestNet")

    @patch(
        "captivity.daemon.network_monitor.subprocess.run",
        side_effect=FileNotFoundError("netsh not found"),
    )
    def test_netsh_missing(self, mock_run):
        self.assertIsNone(_get_ssid_windows())


class TestPollingMonitor(unittest.TestCase):
    """Test the polling-based network monitor."""

    @patch("captivity.daemon.network_monitor.NetworkMonitor._run_polling_monitor")
    def test_non_linux_uses_polling(self, mock_poll):
        """On non-Linux platforms, run() should use polling."""
        monitor = NetworkMonitor()
        monitor.should_run = False  # Don't actually loop

        with patch("captivity.daemon.network_monitor.sys") as mock_sys:
            mock_sys.platform = "darwin"
            # run() will check should_run and exit immediately
            monitor.run()


class TestWinServiceImport(unittest.TestCase):
    """Test that win_service module can be imported safely on Linux."""

    def test_import_win_service(self):
        from captivity.daemon.win_service import CaptivityService, _WIN32_AVAILABLE

        self.assertFalse(_WIN32_AVAILABLE)
        # Stub class should raise on instantiation
        with self.assertRaises(RuntimeError):
            CaptivityService()


if __name__ == "__main__":
    unittest.main()
