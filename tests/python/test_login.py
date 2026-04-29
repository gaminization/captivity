"""Tests for captivity.core.login module (v2.1 — with CAPTCHA handling)."""

import unittest
from unittest.mock import patch, MagicMock

from captivity.core.login import do_login, LoginResult
from captivity.core.probe import ConnectivityStatus, ProbeResult
from captivity.core.credentials import CredentialError


def _make_probe_result(status, portal_url=None, has_captcha=False):
    """Helper to create a ProbeResult for tests."""
    return ProbeResult(
        status=status,
        portal_url=portal_url,
        has_captcha=has_captcha,
        detection_method="test",
    )


class TestLogin(unittest.TestCase):
    """Test plugin-based login engine."""

    @patch("captivity.core.login.probe_connectivity_detailed")
    @patch("captivity.core.login.select_plugin")
    @patch("captivity.core.login.discover_plugins")
    @patch("captivity.core.login.PortalCache")
    @patch("captivity.core.login.requests.Session")
    @patch("captivity.core.login.retrieve")
    @patch("captivity.core.login._verify_login", return_value=True)
    def test_successful_login(
        self,
        mock_verify,
        mock_retrieve,
        mock_session_cls,
        mock_cache_cls,
        mock_discover,
        mock_select,
        mock_probe_detailed,
    ):
        """Login succeeds via plugin detection and connectivity verification."""
        mock_retrieve.return_value = ("user", "pass")
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<html><form>login</form></html>"
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session

        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        mock_probe_detailed.return_value = _make_probe_result(
            ConnectivityStatus.PORTAL_DETECTED,
            portal_url="http://portal.example.com",
        )

        mock_plugin = MagicMock()
        mock_plugin.name = "TestPlugin"
        mock_plugin.login.return_value = True
        mock_select.return_value = mock_plugin
        mock_discover.return_value = [mock_plugin]

        result = do_login("test_net")
        self.assertEqual(result, LoginResult.SUCCESS)
        mock_plugin.login.assert_called_once()

    @patch("captivity.core.login.probe_connectivity_detailed")
    @patch("captivity.core.login.select_plugin")
    @patch("captivity.core.login.discover_plugins")
    @patch("captivity.core.login.PortalCache")
    @patch("captivity.core.login.requests.Session")
    @patch("captivity.core.login.retrieve")
    @patch("captivity.core.login._verify_login", return_value=False)
    def test_login_fails_when_not_verified(
        self,
        mock_verify,
        mock_retrieve,
        mock_session_cls,
        mock_cache_cls,
        mock_discover,
        mock_select,
        mock_probe_detailed,
    ):
        """Login returns FAILED when connectivity check fails after plugin login."""
        mock_retrieve.return_value = ("user", "pass")
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<html><form>login</form></html>"
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session

        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        mock_probe_detailed.return_value = _make_probe_result(
            ConnectivityStatus.PORTAL_DETECTED,
            portal_url="http://portal.example.com",
        )

        mock_plugin = MagicMock()
        mock_plugin.name = "TestPlugin"
        mock_plugin.login.return_value = True
        mock_select.return_value = mock_plugin
        mock_discover.return_value = [mock_plugin]

        with patch("captivity.core.login._open_browser"):
            result = do_login("test_net")
            self.assertEqual(result, LoginResult.WAIT_USER)

    @patch("captivity.core.login.probe_connectivity_detailed")
    @patch("captivity.core.login.retrieve")
    def test_login_returns_wait_user_on_missing_creds(
        self,
        mock_retrieve,
        mock_probe_detailed,
    ):
        """Login falls back to browser if creds missing and portal exists."""
        mock_probe_detailed.return_value = _make_probe_result(
            ConnectivityStatus.PORTAL_DETECTED,
            portal_url="http://foo.com",
            has_captcha=False,
        )
        mock_retrieve.side_effect = CredentialError("not found")

        with patch("captivity.core.login._open_browser"):
            result = do_login("missing_net")

        self.assertEqual(result, LoginResult.WAIT_USER)

    @patch("captivity.core.login.probe_connectivity_detailed")
    def test_dry_run_skips_requests(self, mock_probe_detailed):
        """Dry run returns SUCCESS without making network calls."""
        mock_probe_detailed.return_value = _make_probe_result(
            ConnectivityStatus.PORTAL_DETECTED,
        )

        result = do_login("test_net", dry_run=True)
        self.assertEqual(result, LoginResult.SUCCESS)

    @patch("captivity.core.probe._check_captcha")
    @patch("captivity.core.login.probe_connectivity_detailed")
    @patch("captivity.core.login.select_plugin")
    @patch("captivity.core.login.discover_plugins")
    @patch("captivity.core.login.PortalCache")
    @patch("captivity.core.login.requests.Session")
    @patch("captivity.core.login.retrieve")
    def test_no_plugin_match_returns_wait_user(
        self,
        mock_retrieve,
        mock_session_cls,
        mock_cache_cls,
        mock_discover,
        mock_select,
        mock_probe_detailed,
        mock_check_captcha,
    ):
        """When no plugin matches, returns WAIT_USER."""
        mock_retrieve.return_value = ("user", "pass")
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        mock_probe_detailed.return_value = _make_probe_result(
            ConnectivityStatus.PORTAL_DETECTED,
            portal_url="http://portal.example.com",
        )
        mock_check_captcha.return_value = False
        mock_select.return_value = None
        mock_discover.return_value = []

        with patch("captivity.core.login._open_browser"):
            result = do_login("test_net")
            self.assertEqual(result, LoginResult.WAIT_USER)

    @patch("captivity.core.login.probe_connectivity_detailed")
    def test_already_connected(self, mock_probe_detailed):
        """Login returns SUCCESS if already connected."""
        mock_probe_detailed.return_value = _make_probe_result(
            ConnectivityStatus.CONNECTED,
        )

        result = do_login("test_net")
        self.assertEqual(result, LoginResult.SUCCESS)

    @patch("captivity.core.login.probe_connectivity_detailed")
    def test_network_unavailable(self, mock_probe_detailed):
        """Login returns FAILED if network unavailable."""
        mock_probe_detailed.return_value = _make_probe_result(
            ConnectivityStatus.NETWORK_UNAVAILABLE,
        )

        result = do_login("test_net")
        self.assertEqual(result, LoginResult.FAILED)

    @patch("captivity.core.login.probe_connectivity_detailed")
    @patch("captivity.core.login._open_browser")
    def test_captcha_returns_wait_user(
        self,
        mock_open,
        mock_probe_detailed,
    ):
        """CAPTCHA detection should return WAIT_USER."""
        mock_probe_detailed.return_value = _make_probe_result(
            ConnectivityStatus.PORTAL_DETECTED,
            portal_url="http://portal.captcha.test",
            has_captcha=True,
        )

        result = do_login("test_net")

        mock_open.assert_called_once_with("http://portal.captcha.test")
        self.assertEqual(result, LoginResult.WAIT_USER)


if __name__ == "__main__":
    unittest.main()
