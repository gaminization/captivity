import sys
import unittest
from unittest.mock import MagicMock


class TestTrayIconMocked(unittest.TestCase):
    def setUp(self):
        self.mock_gi = MagicMock()
        self.mock_gtk = MagicMock()
        self.mock_appindicator = MagicMock()

        sys.modules["gi"] = self.mock_gi
        mock_gi_repository = MagicMock()
        sys.modules["gi.repository"] = mock_gi_repository
        sys.modules["gi.repository.Gtk"] = self.mock_gtk
        sys.modules["gi.repository.AppIndicator3"] = self.mock_appindicator
        mock_gi_repository.Gtk = self.mock_gtk
        mock_gi_repository.AppIndicator3 = self.mock_appindicator

        self.mock_gtk.main = MagicMock()
        self.mock_gtk.main_quit = MagicMock()
        self.mock_gtk.Menu = MagicMock
        self.mock_gtk.MenuItem = MagicMock
        self.mock_appindicator.Indicator = MagicMock

        # Force reload so the mock `gi` is used
        import captivity.ui.tray
        import importlib

        importlib.reload(captivity.ui.tray)

    def tearDown(self):
        sys.modules.pop("gi", None)
        sys.modules.pop("gi.repository", None)
        sys.modules.pop("gi.repository.Gtk", None)
        sys.modules.pop("gi.repository.AppIndicator3", None)

    def test_tray_initialization(self):
        import captivity.ui.tray

        mock_event_bus = MagicMock()
        mock_notifier = MagicMock()

        tray = captivity.ui.tray.TrayIcon(mock_event_bus, mock_notifier, "test-net")
        tray._gtk_available = True
        tray.run()
        self.mock_gtk.main.assert_called_once()

        tray._on_quit(None)
        self.mock_gtk.main_quit.assert_called_once()

        # Test event handlers
        tray._on_network_connected(event=None, source="test", ssid="new-net")
        tray._on_portal_detected(event=None, source="test", url="http://test")
        tray._on_login_success(event=None, source="test")
        tray._on_login_failure(event=None, source="test", error="bad")

        # Test menu callbacks
        tray._on_login(None)
        tray._on_probe(None)


if __name__ == "__main__":
    unittest.main()
