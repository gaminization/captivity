"""
WiFi security type detection.

Detects WPA Enterprise (802.1X) networks where captive portal
login should NOT be attempted. Uses nmcli on Linux; returns
UNKNOWN on other platforms (safe default — no false positives).

Usage:
    from captivity.core.wifi import is_enterprise_network
    if is_enterprise_network("eduroam"):
        # Skip captive portal login
"""

import shutil
import subprocess
import sys
from enum import Enum
from typing import Optional

from captivity.utils.logging import get_logger

logger = get_logger("wifi")


class WifiSecurity(Enum):
    """WiFi security classification."""

    OPEN = "open"
    WPA_PSK = "wpa_psk"
    WPA_ENTERPRISE = "wpa_enterprise"
    UNKNOWN = "unknown"


def get_wifi_security(ssid: Optional[str] = None) -> WifiSecurity:
    """Detect the security type of a WiFi network.

    Parses nmcli output to classify the network's authentication
    method. WPA Enterprise (802.1X) networks use EAP authentication
    and do NOT have captive portals.

    Args:
        ssid: Network SSID to check. If None, checks the active connection.

    Returns:
        WifiSecurity enum value.
    """
    if sys.platform != "linux":
        return WifiSecurity.UNKNOWN

    if not shutil.which("nmcli"):
        return WifiSecurity.UNKNOWN

    try:
        if ssid:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "SSID,SECURITY", "device", "wifi", "list"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines():
                parts = line.split(":", 1)
                if len(parts) == 2 and parts[0].strip() == ssid:
                    return _classify_security(parts[1].strip())
        else:
            # Check active connection
            result = subprocess.run(
                [
                    "nmcli",
                    "-t",
                    "-f",
                    "NAME,TYPE,DEVICE",
                    "connection",
                    "show",
                    "--active",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines():
                parts = line.split(":")
                if len(parts) >= 2 and parts[1] == "802-11-wireless":
                    conn_name = parts[0]
                    return _get_connection_security(conn_name)

    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("WiFi security detection failed: %s", exc)

    return WifiSecurity.UNKNOWN


def _classify_security(security_str: str) -> WifiSecurity:
    """Classify security from nmcli SECURITY field output.

    nmcli outputs strings like:
        WPA2        → WPA_PSK
        WPA1 WPA2   → WPA_PSK
        WPA2 802.1X → WPA_ENTERPRISE
        802.1X      → WPA_ENTERPRISE
        (empty)     → OPEN
    """
    sec = security_str.upper()
    if not sec or sec == "--":
        return WifiSecurity.OPEN
    if "802.1X" in sec or "EAP" in sec or "ENTERPRISE" in sec:
        return WifiSecurity.WPA_ENTERPRISE
    if "WPA" in sec or "WEP" in sec:
        return WifiSecurity.WPA_PSK
    return WifiSecurity.UNKNOWN


def _get_connection_security(conn_name: str) -> WifiSecurity:
    """Get security type from an active connection's detailed info."""
    try:
        result = subprocess.run(
            [
                "nmcli",
                "-t",
                "-f",
                "802-11-wireless-security.key-mgmt",
                "connection",
                "show",
                conn_name,
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout.strip().lower()
        if "wpa-eap" in output or "ieee8021x" in output:
            return WifiSecurity.WPA_ENTERPRISE
        if "wpa-psk" in output or "sae" in output:
            return WifiSecurity.WPA_PSK
        if "none" in output or not output:
            return WifiSecurity.OPEN
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("Connection security check failed: %s", exc)

    return WifiSecurity.UNKNOWN


def is_enterprise_network(ssid: Optional[str] = None) -> bool:
    """Check if the network uses WPA Enterprise (802.1X).

    Enterprise networks use EAP-based authentication (e.g. eduroam,
    corporate WPA2-Enterprise) and never have captive portals.
    Attempting captive portal login on such networks is incorrect.

    Args:
        ssid: Network SSID to check.

    Returns:
        True if the network is WPA Enterprise.
    """
    security = get_wifi_security(ssid)
    if security == WifiSecurity.WPA_ENTERPRISE:
        logger.info(
            "Network '%s' is WPA Enterprise (802.1X) — no captive portal expected",
            ssid or "(active)",
        )
        return True
    return False
