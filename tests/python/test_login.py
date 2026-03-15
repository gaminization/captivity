"""Tests for captivity.core.login module."""

import unittest
from unittest.mock import patch, MagicMock

from captivity.core.login import do_login, LoginError
from captivity.core.probe import ConnectivityStatus
from captivity.core.credentials import CredentialError


class TestLogin(unittest.TestCase):
    """Test login engine."""

    @patch("captivity.core.login.probe_connectivity")
    @patch("captivity.core.login.requests.Session")
    @patch("captivity.core.login.retrieve")
    def test_successful_login(self, mock_retrieve, mock_session_cls, mock_probe):
        """Login succeeds when connectivity is verified."""
        mock_retrieve.return_value = ("user", "pass")
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_probe.return_value = (ConnectivityStatus.CONNECTED, None)

        result = do_login("test_net")
        self.assertTrue(result)
        mock_retrieve.assert_called_once_with("test_net")
        mock_session.post.assert_called_once()

    @patch("captivity.core.login.probe_connectivity")
    @patch("captivity.core.login.requests.Session")
    @patch("captivity.core.login.retrieve")
    def test_login_fails_when_not_verified(self, mock_retrieve, mock_session_cls, mock_probe):
        """Login returns False when connectivity check fails."""
        mock_retrieve.return_value = ("user", "pass")
        mock_session_cls.return_value = MagicMock()
        mock_probe.return_value = (ConnectivityStatus.PORTAL_DETECTED, None)

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

    @patch("captivity.core.login.requests.Session")
    @patch("captivity.core.login.retrieve")
    def test_login_error_on_portal_failure(self, mock_retrieve, mock_session_cls):
        """LoginError raised when portal is unreachable."""
        import requests
        mock_retrieve.return_value = ("user", "pass")
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.exceptions.ConnectionError()
        mock_session_cls.return_value = mock_session

        with self.assertRaises(LoginError):
            do_login("test_net")

    @patch("captivity.core.login.probe_connectivity")
    @patch("captivity.core.login.requests.Session")
    @patch("captivity.core.login.retrieve")
    def test_custom_portal_url(self, mock_retrieve, mock_session_cls, mock_probe):
        """Custom portal URL is used for login."""
        mock_retrieve.return_value = ("user", "pass")
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_probe.return_value = (ConnectivityStatus.CONNECTED, None)

        do_login("test_net", portal_url="http://custom-portal.com/login")
        mock_session.get.assert_called_with("http://custom-portal.com/login", timeout=10)
        mock_session.post.assert_called_once()
        post_call = mock_session.post.call_args
        self.assertEqual(post_call[0][0], "http://custom-portal.com/login")


if __name__ == "__main__":
    unittest.main()
