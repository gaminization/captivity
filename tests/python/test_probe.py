"""Tests for captivity.core.probe module."""

import unittest
from unittest.mock import patch, MagicMock

from captivity.core.probe import (
    probe_connectivity,
    ConnectivityStatus,
    ProbeResult,
    PROBE_ENDPOINTS,
    _probe_single,
    _check_captcha,
    _check_portal_html,
)


class TestProbeSingle(unittest.TestCase):
    """Test single endpoint probing."""

    @patch("captivity.core.probe.requests.get")
    def test_connected_on_204(self, mock_get):
        """HTTP 204 → CONNECTED."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {"Content-Length": "0"}
        mock_response.text = ""
        mock_get.return_value = mock_response

        status, redirect, body = _probe_single(
            "http://test/generate_204",
            204,
            None,
        )
        self.assertEqual(status, ConnectivityStatus.CONNECTED)
        self.assertIsNone(redirect)

    @patch("captivity.core.probe.requests.get")
    def test_connected_on_expected_body(self, mock_get):
        """Expected body match → CONNECTED."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "success\n"
        mock_get.return_value = mock_response

        status, redirect, body = _probe_single(
            "http://test/check",
            200,
            "success",
        )
        self.assertEqual(status, ConnectivityStatus.CONNECTED)

    @patch("captivity.core.probe.requests.get")
    def test_portal_on_redirect(self, mock_get):
        """HTTP 302 → PORTAL_DETECTED with redirect URL."""
        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.headers = {"Location": "http://portal.example.com/login"}
        mock_get.return_value = mock_response

        status, redirect, body = _probe_single(
            "http://test/generate_204",
            204,
            None,
        )
        self.assertEqual(status, ConnectivityStatus.PORTAL_DETECTED)
        self.assertEqual(redirect, "http://portal.example.com/login")

    @patch("captivity.core.probe.requests.get")
    def test_portal_on_non_204(self, mock_get):
        """HTTP 200 (unexpected) → PORTAL_DETECTED."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><form>login</form></html>"
        mock_get.return_value = mock_response

        status, redirect, body = _probe_single(
            "http://test/generate_204",
            204,
            None,
        )
        self.assertEqual(status, ConnectivityStatus.PORTAL_DETECTED)
        self.assertIsNotNone(body)

    @patch("captivity.core.probe.requests.get")
    def test_unavailable_on_timeout(self, mock_get):
        """Timeout → NETWORK_UNAVAILABLE."""
        import requests

        mock_get.side_effect = requests.exceptions.Timeout()

        status, redirect, body = _probe_single(
            "http://test/generate_204",
            204,
            None,
        )
        self.assertEqual(status, ConnectivityStatus.NETWORK_UNAVAILABLE)

    @patch("captivity.core.probe.requests.get")
    def test_unavailable_on_connection_error(self, mock_get):
        """ConnectionError → NETWORK_UNAVAILABLE."""
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError()

        status, redirect, body = _probe_single(
            "http://test/generate_204",
            204,
            None,
        )
        self.assertEqual(status, ConnectivityStatus.NETWORK_UNAVAILABLE)

    @patch("captivity.core.probe.requests.get")
    def test_portal_on_ssl_error(self, mock_get):
        """SSLError → PORTAL_DETECTED (portal intercepting TLS)."""
        import requests

        mock_get.side_effect = requests.exceptions.SSLError()

        status, redirect, body = _probe_single(
            "https://test/generate_204",
            204,
            None,
        )
        self.assertEqual(status, ConnectivityStatus.PORTAL_DETECTED)


class TestProbeConnectivity(unittest.TestCase):
    """Test the backward-compatible probe_connectivity function."""

    @patch("captivity.core.probe._probe_single")
    def test_single_url_override(self, mock_probe):
        """probe_connectivity(url=...) uses single probe mode."""
        mock_probe.return_value = (ConnectivityStatus.CONNECTED, None, None)

        status, redirect = probe_connectivity(url="http://custom/check")
        self.assertEqual(status, ConnectivityStatus.CONNECTED)
        self.assertIsNone(redirect)

    @patch("captivity.core.probe._probe_single")
    def test_returns_redirect_url(self, mock_probe):
        """Portal redirect URL is returned."""
        mock_probe.return_value = (
            ConnectivityStatus.PORTAL_DETECTED,
            "http://portal.test/login",
            None,
        )

        status, redirect = probe_connectivity(url="http://test/204")
        self.assertEqual(status, ConnectivityStatus.PORTAL_DETECTED)
        self.assertEqual(redirect, "http://portal.test/login")


class TestProbeEndpoints(unittest.TestCase):
    """Test probe endpoint configuration."""

    def test_endpoints_use_http(self):
        """All probe endpoints must use HTTP (not HTTPS)."""
        for ep in PROBE_ENDPOINTS:
            self.assertTrue(
                ep["url"].startswith("http://"),
                f"Endpoint {ep['name']} uses HTTPS — portals can't intercept",
            )

    def test_endpoints_have_names(self):
        """All endpoints must have names for logging."""
        for ep in PROBE_ENDPOINTS:
            self.assertTrue(ep["name"])

    def test_at_least_two_endpoints(self):
        """Must have at least 2 endpoints for voting."""
        self.assertGreaterEqual(len(PROBE_ENDPOINTS), 2)


class TestCaptchaDetection(unittest.TestCase):
    """Test CAPTCHA detection in HTML."""

    def test_detects_recaptcha(self):
        """Should detect reCAPTCHA."""
        html = '<div class="g-recaptcha" data-sitekey="abc"></div>'
        self.assertTrue(_check_captcha(html))

    def test_detects_captcha_keyword(self):
        """Should detect 'captcha' keyword."""
        html = '<img src="captcha.php" />'
        self.assertTrue(_check_captcha(html))

    def test_no_false_positive(self):
        """Normal login page should not trigger CAPTCHA."""
        html = '<form><input name="user"><input name="pass"></form>'
        self.assertFalse(_check_captcha(html))

    def test_detects_hcaptcha(self):
        """Should detect hCaptcha."""
        html = '<div class="h-captcha" data-sitekey="x"></div>'
        self.assertTrue(_check_captcha(html))


class TestPortalHtmlDetection(unittest.TestCase):
    """Test portal HTML indicator detection."""

    def test_detects_form(self):
        """HTML with <form> should be detected as portal."""
        self.assertTrue(_check_portal_html("<form method='post'>"))

    def test_detects_input(self):
        """HTML with <input> should be detected as portal."""
        self.assertTrue(_check_portal_html('<input type="text" name="user">'))

    def test_detects_captcha(self):
        """HTML with 'captcha' should be detected as portal."""
        self.assertTrue(_check_portal_html("Please complete the captcha"))

    def test_normal_page_not_detected(self):
        """Plain 'success' page should not be detected."""
        self.assertFalse(_check_portal_html("success"))

    def test_detects_wifi_keyword(self):
        """HTML with 'wifi' should be detected as portal."""
        self.assertTrue(_check_portal_html("Connect to WiFi"))


class TestProbeResult(unittest.TestCase):
    """Test ProbeResult dataclass."""

    def test_defaults(self):
        """ProbeResult defaults should be sensible."""
        r = ProbeResult(status=ConnectivityStatus.CONNECTED)
        self.assertIsNone(r.portal_url)
        self.assertFalse(r.has_captcha)
        self.assertIsNone(r.portal_html)
        self.assertEqual(r.probe_details, [])
        self.assertEqual(r.detection_method, "")


if __name__ == "__main__":
    unittest.main()
