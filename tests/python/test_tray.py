"""Tests for captivity.ui.tray module."""

import unittest
from unittest.mock import patch, MagicMock

from captivity.daemon.events import Event, EventBus
from captivity.ui.tray import TrayIcon, is_gtk_available, ICONS


class TestIsGtkAvailable(unittest.TestCase):
    """Test GTK availability check."""

    def test_returns_bool(self):
        """is_gtk_available should return a boolean."""
        result = is_gtk_available()
        self.assertIsInstance(result, bool)


class TestIcons(unittest.TestCase):
    """Test icon mapping."""

    def test_all_states_have_icons(self):
        expected = {"connected", "portal", "offline", "idle", "error"}
        self.assertEqual(set(ICONS.keys()), expected)


class TestTrayIconWithoutGtk(unittest.TestCase):
    """Test TrayIcon behavior when GTK is unavailable."""

    @patch("captivity.ui.tray.is_gtk_available", return_value=False)
    def test_tray_degrades_gracefully(self, mock_gtk):
        event_bus = EventBus()
        notifier = MagicMock()
        tray = TrayIcon(event_bus=event_bus, notifier=notifier)
        self.assertFalse(tray._gtk_available)
        self.assertIsNone(tray._icon)

    @patch("captivity.ui.tray.is_gtk_available", return_value=False)
    def test_run_without_gtk_returns(self, mock_gtk):
        tray = TrayIcon()
        tray.run()  # Should return immediately, not crash


class TestTrayIconEvents(unittest.TestCase):
    """Test event handler wiring."""

    @patch("captivity.ui.tray.is_gtk_available", return_value=False)
    def test_event_handlers_exist(self, mock_gtk):
        event_bus = EventBus()
        notifier = MagicMock()
        tray = TrayIcon(event_bus=event_bus, notifier=notifier, network="TestNet")

        # Test event handlers directly
        tray._on_login_success()
        self.assertEqual(tray.status, "connected")
        notifier.notify_login_success.assert_called_with("TestNet")

    @patch("captivity.ui.tray.is_gtk_available", return_value=False)
    def test_login_failure_handler(self, mock_gtk):
        notifier = MagicMock()
        tray = TrayIcon(notifier=notifier, network="TestNet")
        tray._on_login_failure(error="timeout")
        self.assertEqual(tray.status, "error")
        notifier.notify_login_failure.assert_called_with("TestNet", "timeout")

    @patch("captivity.ui.tray.is_gtk_available", return_value=False)
    def test_portal_detected_handler(self, mock_gtk):
        notifier = MagicMock()
        tray = TrayIcon(notifier=notifier, network="TestNet")
        tray._on_portal_detected()
        self.assertEqual(tray.status, "portal")

    @patch("captivity.ui.tray.is_gtk_available", return_value=False)
    def test_session_expired_handler(self, mock_gtk):
        notifier = MagicMock()
        tray = TrayIcon(notifier=notifier, network="TestNet")
        tray._on_session_expired()
        self.assertEqual(tray.status, "offline")

    @patch("captivity.ui.tray.is_gtk_available", return_value=False)
    def test_network_connected_handler(self, mock_gtk):
        notifier = MagicMock()
        tray = TrayIcon(notifier=notifier)
        tray._on_network_connected()
        self.assertEqual(tray.status, "idle")

    @patch("captivity.ui.tray.is_gtk_available", return_value=False)
    def test_event_bus_integration(self, mock_gtk):
        """Events published to bus should invoke tray handlers."""
        event_bus = EventBus()
        notifier = MagicMock()
        tray = TrayIcon(event_bus=event_bus, notifier=notifier, network="Net")

        # Publish a login success event
        event_bus.publish(Event.LOGIN_SUCCESS)
        self.assertEqual(tray.status, "connected")


if __name__ == "__main__":
    unittest.main()
