"""Tests for captivity.core.wifi — WPA Enterprise detection."""

import unittest
from unittest.mock import patch, MagicMock

from captivity.core.wifi import (
    WifiSecurity,
    get_wifi_security,
    is_enterprise_network,
    _classify_security,
    _get_connection_security,
)


class TestClassifySecurity(unittest.TestCase):
    """Test raw security string classification."""

    def test_open(self):
        self.assertEqual(_classify_security(""), WifiSecurity.OPEN)
        self.assertEqual(_classify_security("--"), WifiSecurity.OPEN)

    def test_wpa_psk(self):
        self.assertEqual(_classify_security("WPA2"), WifiSecurity.WPA_PSK)
        self.assertEqual(_classify_security("WPA1 WPA2"), WifiSecurity.WPA_PSK)
        self.assertEqual(_classify_security("WEP"), WifiSecurity.WPA_PSK)

    def test_enterprise(self):
        self.assertEqual(_classify_security("WPA2 802.1X"), WifiSecurity.WPA_ENTERPRISE)
        self.assertEqual(_classify_security("802.1X"), WifiSecurity.WPA_ENTERPRISE)
        self.assertEqual(_classify_security("WPA2-EAP"), WifiSecurity.WPA_ENTERPRISE)
        self.assertEqual(
            _classify_security("WPA Enterprise"), WifiSecurity.WPA_ENTERPRISE
        )

    def test_unknown(self):
        self.assertEqual(_classify_security("SOMETHING_ELSE"), WifiSecurity.UNKNOWN)


class TestGetWifiSecurity(unittest.TestCase):
    """Test get_wifi_security() with mocked subprocess."""

    @patch("captivity.core.wifi.sys")
    def test_non_linux_returns_unknown(self, mock_sys):
        mock_sys.platform = "darwin"
        self.assertEqual(get_wifi_security("test"), WifiSecurity.UNKNOWN)

    @patch("captivity.core.wifi.shutil.which", return_value=None)
    def test_no_nmcli_returns_unknown(self, mock_which):
        self.assertEqual(get_wifi_security("test"), WifiSecurity.UNKNOWN)

    @patch("captivity.core.wifi.subprocess.run")
    @patch("captivity.core.wifi.shutil.which", return_value="/usr/bin/nmcli")
    def test_ssid_enterprise(self, mock_which, mock_run):
        result = MagicMock()
        result.stdout = "eduroam:WPA2 802.1X\nCafeWifi:WPA2\n"
        mock_run.return_value = result
        self.assertEqual(get_wifi_security("eduroam"), WifiSecurity.WPA_ENTERPRISE)

    @patch("captivity.core.wifi.subprocess.run")
    @patch("captivity.core.wifi.shutil.which", return_value="/usr/bin/nmcli")
    def test_ssid_psk(self, mock_which, mock_run):
        result = MagicMock()
        result.stdout = "CafeWifi:WPA2\n"
        mock_run.return_value = result
        self.assertEqual(get_wifi_security("CafeWifi"), WifiSecurity.WPA_PSK)

    @patch("captivity.core.wifi.subprocess.run")
    @patch("captivity.core.wifi.shutil.which", return_value="/usr/bin/nmcli")
    def test_ssid_not_found(self, mock_which, mock_run):
        result = MagicMock()
        result.stdout = "OtherNet:WPA2\n"
        mock_run.return_value = result
        self.assertEqual(get_wifi_security("Missing"), WifiSecurity.UNKNOWN)

    @patch("captivity.core.wifi.subprocess.run")
    @patch("captivity.core.wifi.shutil.which", return_value="/usr/bin/nmcli")
    def test_timeout_returns_unknown(self, mock_which, mock_run):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="nmcli", timeout=5)
        self.assertEqual(get_wifi_security("test"), WifiSecurity.UNKNOWN)

    @patch("captivity.core.wifi._get_connection_security")
    @patch("captivity.core.wifi.subprocess.run")
    @patch("captivity.core.wifi.shutil.which", return_value="/usr/bin/nmcli")
    def test_active_connection(self, mock_which, mock_run, mock_conn_sec):
        result = MagicMock()
        result.stdout = "MyWifi:802-11-wireless:wlan0\n"
        mock_run.return_value = result
        mock_conn_sec.return_value = WifiSecurity.WPA_PSK
        self.assertEqual(get_wifi_security(None), WifiSecurity.WPA_PSK)


class TestGetConnectionSecurity(unittest.TestCase):
    @patch("captivity.core.wifi.subprocess.run")
    def test_eap(self, mock_run):
        result = MagicMock()
        result.stdout = "802-11-wireless-security.key-mgmt:wpa-eap\n"
        mock_run.return_value = result
        self.assertEqual(_get_connection_security("MyNet"), WifiSecurity.WPA_ENTERPRISE)

    @patch("captivity.core.wifi.subprocess.run")
    def test_psk(self, mock_run):
        result = MagicMock()
        result.stdout = "802-11-wireless-security.key-mgmt:wpa-psk\n"
        mock_run.return_value = result
        self.assertEqual(_get_connection_security("MyNet"), WifiSecurity.WPA_PSK)

    @patch("captivity.core.wifi.subprocess.run")
    def test_sae(self, mock_run):
        result = MagicMock()
        result.stdout = "802-11-wireless-security.key-mgmt:sae\n"
        mock_run.return_value = result
        self.assertEqual(_get_connection_security("MyNet"), WifiSecurity.WPA_PSK)

    @patch("captivity.core.wifi.subprocess.run")
    def test_open(self, mock_run):
        result = MagicMock()
        result.stdout = "802-11-wireless-security.key-mgmt:none\n"
        mock_run.return_value = result
        self.assertEqual(_get_connection_security("MyNet"), WifiSecurity.OPEN)


class TestIsEnterpriseNetwork(unittest.TestCase):
    @patch("captivity.core.wifi.get_wifi_security")
    def test_enterprise_true(self, mock_get):
        mock_get.return_value = WifiSecurity.WPA_ENTERPRISE
        self.assertTrue(is_enterprise_network("eduroam"))

    @patch("captivity.core.wifi.get_wifi_security")
    def test_psk_false(self, mock_get):
        mock_get.return_value = WifiSecurity.WPA_PSK
        self.assertFalse(is_enterprise_network("HomeNet"))

    @patch("captivity.core.wifi.get_wifi_security")
    def test_unknown_false(self, mock_get):
        mock_get.return_value = WifiSecurity.UNKNOWN
        self.assertFalse(is_enterprise_network("SomeNet"))


class TestEnterpriseLoginShortCircuit(unittest.TestCase):
    """Test that enterprise networks short-circuit do_login()."""

    @patch("captivity.core.wifi.is_enterprise_network", return_value=True)
    def test_enterprise_returns_failed(self, mock_is_ent):
        from captivity.core.login import do_login, LoginResult

        result = do_login(network="eduroam", dry_run=True)
        self.assertEqual(result, LoginResult.FAILED)


if __name__ == "__main__":
    unittest.main()
