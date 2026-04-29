"""Tests for captivity.core.fingerprint module."""

import unittest
from unittest.mock import patch, MagicMock

from captivity.core.fingerprint import (
    NetworkFingerprint,
    extract_portal_domain,
    hash_content,
    get_default_gateway,
    get_gateway_mac,
    capture_fingerprint,
)


class TestNetworkFingerprint(unittest.TestCase):
    """Test NetworkFingerprint class."""

    def test_create_basic(self):
        fp = NetworkFingerprint(ssid="TestNet")
        self.assertEqual(fp.ssid, "TestNet")
        self.assertEqual(fp.gateway_ip, "")

    def test_fingerprint_id_deterministic(self):
        fp1 = NetworkFingerprint(
            ssid="Net", gateway_ip="10.0.0.1", portal_domain="portal.com"
        )
        fp2 = NetworkFingerprint(
            ssid="Net", gateway_ip="10.0.0.1", portal_domain="portal.com"
        )
        self.assertEqual(fp1.fingerprint_id, fp2.fingerprint_id)

    def test_fingerprint_id_differs(self):
        fp1 = NetworkFingerprint(ssid="Net1", gateway_ip="10.0.0.1")
        fp2 = NetworkFingerprint(ssid="Net2", gateway_ip="10.0.0.1")
        self.assertNotEqual(fp1.fingerprint_id, fp2.fingerprint_id)

    def test_is_complete_with_gateway(self):
        fp = NetworkFingerprint(ssid="Net", gateway_ip="10.0.0.1")
        self.assertTrue(fp.is_complete)

    def test_is_complete_with_portal(self):
        fp = NetworkFingerprint(ssid="Net", portal_domain="portal.com")
        self.assertTrue(fp.is_complete)

    def test_is_not_complete_ssid_only(self):
        fp = NetworkFingerprint(ssid="Net")
        self.assertFalse(fp.is_complete)

    def test_matches_exact(self):
        fp1 = NetworkFingerprint(
            ssid="Net",
            gateway_ip="10.0.0.1",
            gateway_mac="aa:bb:cc:dd:ee:ff",
            portal_domain="portal.com",
        )
        fp2 = NetworkFingerprint(
            ssid="Net",
            gateway_ip="10.0.0.1",
            gateway_mac="AA:BB:CC:DD:EE:FF",
            portal_domain="portal.com",
        )
        self.assertAlmostEqual(fp1.matches(fp2), 1.0)

    def test_matches_different_ssid(self):
        fp1 = NetworkFingerprint(ssid="Net1", gateway_ip="10.0.0.1")
        fp2 = NetworkFingerprint(ssid="Net2", gateway_ip="10.0.0.1")
        self.assertEqual(fp1.matches(fp2), 0.0)

    def test_matches_partial(self):
        fp1 = NetworkFingerprint(
            ssid="Net", gateway_ip="10.0.0.1", portal_domain="portal.com"
        )
        fp2 = NetworkFingerprint(
            ssid="Net", gateway_ip="10.0.0.1", portal_domain="other.com"
        )
        score = fp1.matches(fp2)
        self.assertGreater(score, 0.5)
        self.assertLess(score, 1.0)

    def test_to_dict_from_dict_roundtrip(self):
        fp = NetworkFingerprint(
            ssid="Net",
            gateway_ip="10.0.0.1",
            gateway_mac="aa:bb:cc:dd:ee:ff",
            portal_domain="portal.com",
            content_hash="abc123",
        )
        data = fp.to_dict()
        fp2 = NetworkFingerprint.from_dict(data)
        self.assertEqual(fp.ssid, fp2.ssid)
        self.assertEqual(fp.gateway_ip, fp2.gateway_ip)
        self.assertEqual(fp.gateway_mac, fp2.gateway_mac)

    def test_repr(self):
        fp = NetworkFingerprint(ssid="Net", gateway_ip="10.0.0.1")
        self.assertIn("Net", repr(fp))
        self.assertIn("10.0.0.1", repr(fp))


class TestExtractPortalDomain(unittest.TestCase):
    """Test extract_portal_domain function."""

    def test_http_url(self):
        self.assertEqual(
            extract_portal_domain("http://portal.example.com/login"),
            "portal.example.com",
        )

    def test_https_url(self):
        self.assertEqual(
            extract_portal_domain("https://login.wifi.net/auth"),
            "login.wifi.net",
        )

    def test_empty_string(self):
        self.assertEqual(extract_portal_domain(""), "")

    def test_no_scheme(self):
        self.assertEqual(extract_portal_domain("portal.com/login"), "")


class TestHashContent(unittest.TestCase):
    """Test hash_content function."""

    def test_deterministic(self):
        self.assertEqual(hash_content("hello"), hash_content("hello"))

    def test_different_content(self):
        self.assertNotEqual(hash_content("hello"), hash_content("world"))

    def test_length(self):
        self.assertEqual(len(hash_content("test")), 32)


class TestGetDefaultGateway(unittest.TestCase):
    """Test get_default_gateway function."""

    @patch("captivity.core.fingerprint.subprocess.run")
    def test_parses_gateway(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="default via 192.168.1.1 dev wlan0",
            returncode=0,
        )
        self.assertEqual(get_default_gateway(), "192.168.1.1")

    @patch("captivity.core.fingerprint.subprocess.run")
    def test_no_default_route(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        self.assertIsNone(get_default_gateway())


class TestGetGatewayMac(unittest.TestCase):
    """Test get_gateway_mac function."""

    @patch("captivity.core.fingerprint.subprocess.run")
    def test_parses_mac(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="192.168.1.1 dev wlan0 lladdr aa:bb:cc:dd:ee:ff REACHABLE",
            returncode=0,
        )
        self.assertEqual(get_gateway_mac("192.168.1.1"), "aa:bb:cc:dd:ee:ff")


class TestCaptureFingerprint(unittest.TestCase):
    """Test capture_fingerprint function."""

    @patch(
        "captivity.core.fingerprint.get_gateway_mac", return_value="aa:bb:cc:dd:ee:ff"
    )
    @patch("captivity.core.fingerprint.get_default_gateway", return_value="10.0.0.1")
    def test_captures_all(self, mock_gw, mock_mac):
        fp = capture_fingerprint(
            ssid="TestNet",
            portal_url="http://portal.com/login",
            portal_content="<html>Login</html>",
        )
        self.assertEqual(fp.ssid, "TestNet")
        self.assertEqual(fp.gateway_ip, "10.0.0.1")
        self.assertEqual(fp.gateway_mac, "aa:bb:cc:dd:ee:ff")
        self.assertEqual(fp.portal_domain, "portal.com")
        self.assertTrue(len(fp.content_hash) > 0)


if __name__ == "__main__":
    unittest.main()
