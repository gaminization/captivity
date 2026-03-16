"""Tests for captivity.daemon.dbus_monitor module."""

import unittest
from unittest.mock import patch, MagicMock

from captivity.daemon.dbus_monitor import (
    NMConnectivityState,
    is_dbus_available,
    get_nm_connectivity,
    get_active_wifi_ssid,
    DBusMonitor,
)


class TestNMConnectivityState(unittest.TestCase):
    """Test NM connectivity state enum."""

    def test_states(self):
        self.assertEqual(NMConnectivityState.NONE, 1)
        self.assertEqual(NMConnectivityState.PORTAL, 2)
        self.assertEqual(NMConnectivityState.FULL, 4)


class TestIsDBusAvailable(unittest.TestCase):

    @patch("captivity.daemon.dbus_monitor.shutil.which", return_value="/usr/bin/busctl")
    def test_available(self, mock_which):
        self.assertTrue(is_dbus_available())

    @patch("captivity.daemon.dbus_monitor.shutil.which", return_value=None)
    def test_not_available(self, mock_which):
        self.assertFalse(is_dbus_available())


class TestGetNMConnectivity(unittest.TestCase):

    @patch("captivity.daemon.dbus_monitor.is_dbus_available", return_value=True)
    @patch("captivity.daemon.dbus_monitor.subprocess.run")
    def test_returns_full(self, mock_run, mock_avail):
        result = MagicMock()
        result.returncode = 0
        result.stdout = "u 4\n"
        mock_run.return_value = result

        state = get_nm_connectivity()
        self.assertEqual(state, NMConnectivityState.FULL)

    @patch("captivity.daemon.dbus_monitor.is_dbus_available", return_value=True)
    @patch("captivity.daemon.dbus_monitor.subprocess.run")
    def test_returns_portal(self, mock_run, mock_avail):
        result = MagicMock()
        result.returncode = 0
        result.stdout = "u 2\n"
        mock_run.return_value = result

        state = get_nm_connectivity()
        self.assertEqual(state, NMConnectivityState.PORTAL)

    @patch("captivity.daemon.dbus_monitor.is_dbus_available", return_value=False)
    def test_returns_none_without_dbus(self, mock_avail):
        state = get_nm_connectivity()
        self.assertIsNone(state)


class TestGetActiveWifiSSID(unittest.TestCase):

    @patch("captivity.daemon.dbus_monitor.shutil.which", return_value="/usr/bin/nmcli")
    @patch("captivity.daemon.dbus_monitor.subprocess.run")
    def test_returns_ssid(self, mock_run, mock_which):
        result = MagicMock()
        result.stdout = "no:OtherNet\nyes:MyWiFi\n"
        mock_run.return_value = result

        ssid = get_active_wifi_ssid()
        self.assertEqual(ssid, "MyWiFi")

    @patch("captivity.daemon.dbus_monitor.shutil.which", return_value="/usr/bin/nmcli")
    @patch("captivity.daemon.dbus_monitor.subprocess.run")
    def test_returns_none_when_disconnected(self, mock_run, mock_which):
        result = MagicMock()
        result.stdout = "no:SomeNet\n"
        mock_run.return_value = result

        ssid = get_active_wifi_ssid()
        self.assertIsNone(ssid)

    @patch("captivity.daemon.dbus_monitor.shutil.which", return_value=None)
    def test_returns_none_without_nmcli(self, mock_which):
        ssid = get_active_wifi_ssid()
        self.assertIsNone(ssid)


class TestDBusMonitor(unittest.TestCase):

    @patch("captivity.daemon.dbus_monitor.is_dbus_available", return_value=True)
    def test_available_when_dbus_present(self, mock_avail):
        monitor = DBusMonitor()
        self.assertTrue(monitor.available)

    @patch("captivity.daemon.dbus_monitor.is_dbus_available", return_value=False)
    def test_unavailable_without_dbus(self, mock_avail):
        monitor = DBusMonitor()
        self.assertFalse(monitor.available)

    @patch("captivity.daemon.dbus_monitor.get_nm_connectivity")
    @patch("captivity.daemon.dbus_monitor.is_dbus_available", return_value=True)
    def test_detects_state_change(self, mock_avail, mock_conn):
        monitor = DBusMonitor()
        mock_conn.return_value = NMConnectivityState.PORTAL

        new_state = monitor.check_connectivity_changed()
        self.assertEqual(new_state, NMConnectivityState.PORTAL)

    @patch("captivity.daemon.dbus_monitor.get_nm_connectivity")
    @patch("captivity.daemon.dbus_monitor.is_dbus_available", return_value=True)
    def test_no_change_returns_none(self, mock_avail, mock_conn):
        monitor = DBusMonitor()
        mock_conn.return_value = NMConnectivityState.FULL

        monitor.check_connectivity_changed()  # First call sets state
        result = monitor.check_connectivity_changed()  # Same state
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
