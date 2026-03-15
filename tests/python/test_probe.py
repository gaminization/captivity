"""Tests for captivity.core.probe module."""

import unittest
from unittest.mock import patch, MagicMock

from captivity.core.probe import (
    probe_connectivity,
    ConnectivityStatus,
    PROBE_URL,
)


class TestProbeConnectivity(unittest.TestCase):
    """Test connectivity probing."""

    @patch("captivity.core.probe.requests.get")
    def test_connected_returns_status_on_204(self, mock_get):
        """HTTP 204 → CONNECTED."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response

        status, redirect = probe_connectivity()
        self.assertEqual(status, ConnectivityStatus.CONNECTED)
        self.assertIsNone(redirect)

    @patch("captivity.core.probe.requests.get")
    def test_portal_detected_on_302(self, mock_get):
        """HTTP 302 → PORTAL_DETECTED with redirect URL."""
        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.headers = {"Location": "http://portal.example.com/login"}
        mock_get.return_value = mock_response

        status, redirect = probe_connectivity()
        self.assertEqual(status, ConnectivityStatus.PORTAL_DETECTED)
        self.assertEqual(redirect, "http://portal.example.com/login")

    @patch("captivity.core.probe.requests.get")
    def test_portal_detected_on_200(self, mock_get):
        """HTTP 200 (portal HTML) → PORTAL_DETECTED."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        status, redirect = probe_connectivity()
        self.assertEqual(status, ConnectivityStatus.PORTAL_DETECTED)
        self.assertIsNone(redirect)

    @patch("captivity.core.probe.requests.get")
    def test_network_unavailable_on_timeout(self, mock_get):
        """Timeout → NETWORK_UNAVAILABLE."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        status, redirect = probe_connectivity()
        self.assertEqual(status, ConnectivityStatus.NETWORK_UNAVAILABLE)
        self.assertIsNone(redirect)

    @patch("captivity.core.probe.requests.get")
    def test_network_unavailable_on_connection_error(self, mock_get):
        """ConnectionError → NETWORK_UNAVAILABLE."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()

        status, redirect = probe_connectivity()
        self.assertEqual(status, ConnectivityStatus.NETWORK_UNAVAILABLE)
        self.assertIsNone(redirect)

    @patch("captivity.core.probe.requests.get")
    def test_portal_detected_on_301(self, mock_get):
        """HTTP 301 → PORTAL_DETECTED."""
        mock_response = MagicMock()
        mock_response.status_code = 301
        mock_response.headers = {"Location": "http://portal.test"}
        mock_get.return_value = mock_response

        status, redirect = probe_connectivity()
        self.assertEqual(status, ConnectivityStatus.PORTAL_DETECTED)

    @patch("captivity.core.probe.requests.get")
    def test_uses_correct_probe_url(self, mock_get):
        """Probe uses the default generate_204 endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response

        probe_connectivity()
        mock_get.assert_called_once_with(
            PROBE_URL,
            timeout=5,
            allow_redirects=False,
        )

    @patch("captivity.core.probe.requests.get")
    def test_custom_url(self, mock_get):
        """Custom probe URL is used when specified."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response

        probe_connectivity(url="http://custom.probe/check")
        mock_get.assert_called_once_with(
            "http://custom.probe/check",
            timeout=5,
            allow_redirects=False,
        )


if __name__ == "__main__":
    unittest.main()
