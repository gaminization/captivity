"""
NetworkManager DBus monitor for connectivity events.

Listens to:
    - org.freedesktop.NetworkManager: connectivity state changes
    - org.freedesktop.login1.Manager: PrepareForSleep (system resume)

Falls back to polling if DBus is unavailable.

Note: This module uses subprocess to call `dbus-monitor` and
`busctl` to avoid requiring the `dbus-python` dependency.
If dbus is not available, the daemon will fall back to polling.
"""

import subprocess
import shutil
from enum import IntEnum
from typing import Optional

from captivity.utils.logging import get_logger

logger = get_logger("dbus_monitor")


class NMConnectivityState(IntEnum):
    """NetworkManager connectivity states.

    Maps to org.freedesktop.NetworkManager.ConnectivityState.
    """
    UNKNOWN = 0
    NONE = 1
    PORTAL = 2
    LIMITED = 3
    FULL = 4


def is_dbus_available() -> bool:
    """Check if DBus tools are available on the system."""
    return shutil.which("busctl") is not None


def get_nm_connectivity() -> Optional[NMConnectivityState]:
    """Query current NetworkManager connectivity state via busctl.

    Returns:
        NMConnectivityState, or None if query fails.
    """
    if not is_dbus_available():
        return None

    try:
        result = subprocess.run(
            [
                "busctl", "get-property",
                "org.freedesktop.NetworkManager",
                "/org/freedesktop/NetworkManager",
                "org.freedesktop.NetworkManager",
                "Connectivity",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            logger.debug("busctl query failed: %s", result.stderr.strip())
            return None

        # Output format: "u 4" (type + value)
        parts = result.stdout.strip().split()
        if len(parts) >= 2:
            state = int(parts[1])
            return NMConnectivityState(state)

    except (subprocess.TimeoutExpired, ValueError, OSError) as exc:
        logger.debug("Failed to query NM connectivity: %s", exc)

    return None


def get_active_wifi_ssid() -> Optional[str]:
    """Get the SSID of the currently active WiFi connection.

    Uses nmcli to query the active WiFi connection.

    Returns:
        SSID string, or None if not connected to WiFi.
    """
    if not shutil.which("nmcli"):
        return None

    try:
        result = subprocess.run(
            [
                "nmcli", "-t", "-f", "ACTIVE,SSID",
                "device", "wifi", "list",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        for line in result.stdout.splitlines():
            if line.startswith("yes:"):
                ssid = line.split(":", 1)[1].strip()
                if ssid:
                    return ssid

    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("Failed to get WiFi SSID: %s", exc)

    return None


def check_system_just_resumed() -> bool:
    """Check if the system recently resumed from suspend.

    Uses systemd's sleep inhibitor state to detect resume events.
    This is a one-shot check, not a continuous monitor.

    Returns:
        True if system appears to have just resumed.
    """
    if not is_dbus_available():
        return False

    try:
        result = subprocess.run(
            [
                "busctl", "get-property",
                "org.freedesktop.login1",
                "/org/freedesktop/login1",
                "org.freedesktop.login1.Manager",
                "PreparingForSleep",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Output format: "b false"
        return result.returncode == 0 and "false" in result.stdout

    except (subprocess.TimeoutExpired, OSError):
        return False


class DBusMonitor:
    """Monitors NetworkManager state changes.

    Provides methods to check connectivity state and WiFi status
    without requiring a running event loop. The daemon runner
    calls these methods during its probe cycle.

    Attributes:
        available: Whether DBus tools are available.
        last_state: Last known connectivity state.
    """

    def __init__(self) -> None:
        self.available = is_dbus_available()
        self.last_state: Optional[NMConnectivityState] = None

        if self.available:
            logger.info("DBus tools available — enhanced monitoring enabled")
        else:
            logger.info("DBus tools not available — using polling fallback")

    def check_connectivity_changed(self) -> Optional[NMConnectivityState]:
        """Check if connectivity state has changed since last poll.

        Returns:
            New state if changed, None if unchanged or unavailable.
        """
        if not self.available:
            return None

        current = get_nm_connectivity()
        if current is None:
            return None

        if current != self.last_state:
            previous = self.last_state
            self.last_state = current
            logger.info(
                "Connectivity changed: %s → %s",
                previous.name if previous else "UNKNOWN",
                current.name,
            )
            return current

        return None

    @property
    def is_portal(self) -> bool:
        """Check if NM reports a captive portal."""
        state = get_nm_connectivity()
        return state == NMConnectivityState.PORTAL

    @property
    def is_connected(self) -> bool:
        """Check if NM reports full connectivity."""
        state = get_nm_connectivity()
        return state == NMConnectivityState.FULL

    @property
    def wifi_ssid(self) -> Optional[str]:
        """Get current WiFi SSID."""
        return get_active_wifi_ssid()
