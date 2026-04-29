"""
Bandwidth usage monitor.

Reads network interface statistics from /proc/net/dev to
track bytes transmitted and received during WiFi sessions.

This is a zero-dependency, zero-overhead approach that
reads kernel counters directly.
"""

import re
from typing import Optional

from captivity.utils.logging import get_logger

logger = get_logger("bandwidth")

PROC_NET_DEV = "/proc/net/dev"


class InterfaceStats:
    """Network interface byte counters.

    Attributes:
        interface: Network interface name.
        rx_bytes: Bytes received.
        tx_bytes: Bytes transmitted.
    """

    def __init__(self, interface: str, rx_bytes: int = 0, tx_bytes: int = 0) -> None:
        self.interface = interface
        self.rx_bytes = rx_bytes
        self.tx_bytes = tx_bytes

    @property
    def total_bytes(self) -> int:
        """Total bytes (rx + tx)."""
        return self.rx_bytes + self.tx_bytes

    def __sub__(self, other: "InterfaceStats") -> "InterfaceStats":
        """Calculate the difference between two snapshots."""
        return InterfaceStats(
            interface=self.interface,
            rx_bytes=self.rx_bytes - other.rx_bytes,
            tx_bytes=self.tx_bytes - other.tx_bytes,
        )

    def __repr__(self) -> str:
        return (
            f"InterfaceStats({self.interface!r}, "
            f"rx={format_bytes(self.rx_bytes)}, "
            f"tx={format_bytes(self.tx_bytes)})"
        )


def format_bytes(n: int) -> str:
    """Format byte count to human-readable string.

    Args:
        n: Number of bytes.

    Returns:
        Formatted string (e.g. '1.5 MB').
    """
    if n < 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def read_interface_stats(
    interface: str, proc_path: str = PROC_NET_DEV
) -> Optional[InterfaceStats]:
    """Read current byte counters for a network interface.

    Parses /proc/net/dev which contains kernel-level
    network statistics for all interfaces.

    Args:
        interface: Interface name (e.g. 'wlan0', 'wlp2s0').
        proc_path: Path to proc net dev (for testing).

    Returns:
        InterfaceStats, or None if interface not found.
    """
    try:
        with open(proc_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{interface}:"):
                    parts = line.split(":")
                    if len(parts) < 2:
                        continue
                    fields = parts[1].split()
                    if len(fields) >= 9:
                        rx_bytes = int(fields[0])
                        tx_bytes = int(fields[8])
                        return InterfaceStats(
                            interface=interface,
                            rx_bytes=rx_bytes,
                            tx_bytes=tx_bytes,
                        )
    except (OSError, ValueError) as exc:
        logger.debug("Failed to read interface stats: %s", exc)

    return None


def detect_wifi_interface(proc_path: str = PROC_NET_DEV) -> Optional[str]:
    """Detect the WiFi interface name.

    Looks for common wireless interface patterns
    (wlan*, wlp*, wlx*).

    Args:
        proc_path: Path to proc net dev (for testing).

    Returns:
        Interface name, or None if not found.
    """
    wifi_patterns = re.compile(r"^\s*(wl\w+):")
    try:
        with open(proc_path, "r") as f:
            for line in f:
                match = wifi_patterns.match(line)
                if match:
                    return match.group(1)
    except OSError:
        pass
    return None


class BandwidthMonitor:
    """Tracks bandwidth usage for a WiFi interface.

    Takes periodic snapshots of interface counters to
    calculate session bandwidth usage.

    Attributes:
        interface: Monitored interface name.
        baseline: Byte counters at session start.
    """

    def __init__(
        self, interface: Optional[str] = None, proc_path: str = PROC_NET_DEV
    ) -> None:
        self.interface = interface or detect_wifi_interface(proc_path) or ""
        self._proc_path = proc_path
        self.baseline: Optional[InterfaceStats] = None

        if self.interface:
            logger.info("Monitoring bandwidth on '%s'", self.interface)
        else:
            logger.info("No WiFi interface detected for bandwidth monitoring")

    def start_session(self) -> None:
        """Record baseline counters at session start."""
        if self.interface:
            self.baseline = read_interface_stats(self.interface, self._proc_path)

    def get_session_usage(self) -> Optional[InterfaceStats]:
        """Get bandwidth used since session start.

        Returns:
            InterfaceStats with usage delta, or None.
        """
        if not self.interface or not self.baseline:
            return None

        current = read_interface_stats(self.interface, self._proc_path)
        if not current:
            return None

        return current - self.baseline

    def get_current_stats(self) -> Optional[InterfaceStats]:
        """Get current absolute interface stats.

        Returns:
            InterfaceStats with total counters.
        """
        if not self.interface:
            return None
        return read_interface_stats(self.interface, self._proc_path)
