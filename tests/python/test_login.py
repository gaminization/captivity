"""Tests for captivity.core.login module (v1.0 — plugin-based)."""

import unittest
from unittest.mock import patch, MagicMock, PropertyMock

from captivity.core.login import do_login, LoginError
from captivity.core.probe import ConnectivityStatus
from captivity.core.credentials import CredentialError


class TestLogin(unittest.TestCase):
    """Test plugin-based login engine."""

    @patch("captivity.core.login.probe_connectivity")
    @patch("captivity.core.login.select_plugin")
    @patch("captivity.core.login.discover_plugins")
    @patch("captivity.core.login.PortalCache")
    @patch("captivity.core.login.requests.Session")
    @patch("captivity.core.login.retrieve")
    def test_successful_login(
        self, mock_retrieve, mock_session_cls, mock_cache_cls,
        mock_discover, mock_select, mock_probe,
    ):
        """Login succeeds via plugin detection and connectivity verification."""
        mock_retrieve.return_value = ("user", "pass")
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        # First probe call returns portal redirect, second returns connected
        mock_probe.side_effect = [
            (ConnectivityStatus.PORTAL_DETECTED, "http://portal.example.com"),
            (ConnectivityStatus.CONNECTED, None),
        ]

        mock_plugin = MagicMock()
        mock_plugin.name = "TestPlugin"
        mock_plugin.login.return_value = True
        mock_select.return_value = mock_plugin
        mock_discover.return_value = [mock_plugin]

        result = do_login("test_net")
        self.assertTrue(result)
        mock_plugin.login.assert_called_once()

    @patch("captivity.core.login.probe_connectivity")
    @patch("captivity.core.login.select_plugin")
    @patch("captivity.core.login.discover_plugins")
    @patch("captivity.core.login.PortalCache")
    @patch("captivity.core.login.requests.Session")
    @patch("captivity.core.login.retrieve")
    def test_login_fails_when_not_verified(
        self, mock_retrieve, mock_session_cls, mock_cache_cls,
        mock_discover, mock_select, mock_probe,
    ):
        """Login returns False when connectivity check fails after plugin login."""
        mock_retrieve.return_value = ("user", "pass")
        mock_session_cls.return_value = MagicMock()

        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        mock_probe.side_effect = [
            (ConnectivityStatus.PORTAL_DETECTED, "http://portal.example.com"),
            (ConnectivityStatus.PORTAL_DETECTED, None),
        ]

        mock_plugin = MagicMock()
        mock_plugin.name = "TestPlugin"
        mock_plugin.login.return_value = True
        mock_select.return_value = mock_plugin
        mock_discover.return_value = [mock_plugin]

        result = do_login("test_net")
        self.assertFalse(result)

    @patch("captivity.core.login.retrieve")
    def test_login_raises_on_missing_creds(self, mock_retrieve):
        """Login raises CredentialError when creds not found."""
        mock_retrieve.side_effect = CredentialError("not found")

        with self.assertRaises(CredentialError):
            do_login("missing_net")

    @patch("captivity.core.login.retrieve")
    def test_dry_run_skips_requests(self, mock_retrieve):
        """Dry run returns True without making network calls."""
        mock_retrieve.return_value = ("user", "pass")

        result = do_login("test_net", dry_run=True)
        self.assertTrue(result)

    @patch("captivity.core.login.select_plugin")
    @patch("captivity.core.login.discover_plugins")
    @patch("captivity.core.login.probe_connectivity")
    @patch("captivity.core.login.PortalCache")
    @patch("captivity.core.login.requests.Session")
    @patch("captivity.core.login.retrieve")
    def test_no_plugin_match_raises(
        self, mock_retrieve, mock_session_cls, mock_cache_cls,
        mock_probe, mock_discover, mock_select,
    ):
        """LoginError raised when no plugin matches the portal."""
        mock_retrieve.return_value = ("user", "pass")
        mock_session_cls.return_value = MagicMock()

        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        mock_probe.return_value = (
            ConnectivityStatus.PORTAL_DETECTED, "http://portal.example.com",
        )
        mock_select.return_value = None
        mock_discover.return_value = []

        with self.assertRaises(LoginError):
            do_login("test_net")

    @patch("captivity.core.login.probe_connectivity")
    @patch("captivity.core.login.select_plugin")
    @patch("captivity.core.login.discover_plugins")
    @patch("captivity.core.login.PortalCache")
    @patch("captivity.core.login.requests.Session")
    @patch("captivity.core.login.retrieve")
    def test_custom_portal_url(
        self, mock_retrieve, mock_session_cls, mock_cache_cls,
        mock_discover, mock_select, mock_probe,
    ):
        """Custom portal URL bypasses probe detection."""
        mock_retrieve.return_value = ("user", "pass")
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        # probe_connectivity only called once (for verification)
        mock_probe.return_value = (ConnectivityStatus.CONNECTED, None)

        mock_plugin = MagicMock()
        mock_plugin.name = "TestPlugin"
        mock_plugin.login.return_value = True
        mock_select.return_value = mock_plugin
        mock_discover.return_value = [mock_plugin]

        do_login("test_net", portal_url="http://custom-portal.com/login")
        mock_session.get.assert_called_with(
            "http://custom-portal.com/login", timeout=10,
        )


if __name__ == "__main__":
    unittest.main()
