"""
Connection statistics and history database.

Aggregates telemetry data from session tracker and bandwidth
monitor into a persistent statistics store:
  - Total sessions, uptime, bandwidth
  - Reconnect count and success/failure rates
  - Per-network statistics
  - Connection event history

Stored at: ~/.local/share/captivity/stats.json
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

from captivity.utils.logging import get_logger

logger = get_logger("stats")

STATS_DIR = Path(
    os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
) / "captivity"
STATS_FILE = STATS_DIR / "stats.json"

# Maximum history entries kept
MAX_HISTORY = 500


class ConnectionEvent:
    """A single connection event in the history.

    Attributes:
        timestamp: When the event occurred.
        event_type: Type of event (login_success, login_failure, etc.).
        network: Network SSID.
        details: Additional event details.
    """

    def __init__(
        self,
        event_type: str,
        network: str = "",
        details: str = "",
        timestamp: Optional[float] = None,
    ) -> None:
        self.timestamp = timestamp or time.time()
        self.event_type = event_type
        self.network = network
        self.details = details

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "network": self.network,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConnectionEvent":
        return cls(
            event_type=data["event_type"],
            network=data.get("network", ""),
            details=data.get("details", ""),
            timestamp=data.get("timestamp"),
        )


class NetworkStats:
    """Per-network statistics.

    Attributes:
        ssid: Network SSID.
        login_successes: Number of successful logins.
        login_failures: Number of failed login attempts.
        total_uptime: Total session uptime in seconds.
        total_rx_bytes: Total bytes received.
        total_tx_bytes: Total bytes transmitted.
        reconnect_count: Number of reconnections.
    """

    def __init__(self, ssid: str) -> None:
        self.ssid = ssid
        self.login_successes = 0
        self.login_failures = 0
        self.total_uptime = 0.0
        self.total_rx_bytes = 0
        self.total_tx_bytes = 0
        self.reconnect_count = 0

    @property
    def success_rate(self) -> float:
        """Login success rate (0.0 to 1.0)."""
        total = self.login_successes + self.login_failures
        return self.login_successes / total if total > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "ssid": self.ssid,
            "login_successes": self.login_successes,
            "login_failures": self.login_failures,
            "total_uptime": self.total_uptime,
            "total_rx_bytes": self.total_rx_bytes,
            "total_tx_bytes": self.total_tx_bytes,
            "reconnect_count": self.reconnect_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NetworkStats":
        s = cls(ssid=data["ssid"])
        s.login_successes = data.get("login_successes", 0)
        s.login_failures = data.get("login_failures", 0)
        s.total_uptime = data.get("total_uptime", 0.0)
        s.total_rx_bytes = data.get("total_rx_bytes", 0)
        s.total_tx_bytes = data.get("total_tx_bytes", 0)
        s.reconnect_count = data.get("reconnect_count", 0)
        return s


class StatsDatabase:
    """Persistent connection statistics database.

    Aggregates session, bandwidth, and event data
    into per-network statistics and a global event history.
    """

    def __init__(self, stats_file: Optional[Path] = None) -> None:
        self.stats_file = stats_file or STATS_FILE
        self._networks: dict[str, NetworkStats] = {}
        self._history: list[ConnectionEvent] = []
        self._load()

    def _load(self) -> None:
        """Load stats from disk."""
        if not self.stats_file.exists():
            return
        try:
            with open(self.stats_file, "r") as f:
                data = json.load(f)
            for key, ns_data in data.get("networks", {}).items():
                self._networks[key] = NetworkStats.from_dict(ns_data)
            for ev_data in data.get("history", []):
                self._history.append(ConnectionEvent.from_dict(ev_data))
            logger.debug("Loaded stats: %d networks, %d events",
                         len(self._networks), len(self._history))
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Stats corrupted, resetting: %s", exc)
            self._networks = {}
            self._history = []

    def _save(self) -> None:
        """Persist stats to disk."""
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "networks": {k: v.to_dict() for k, v in self._networks.items()},
            "history": [e.to_dict() for e in self._history[-MAX_HISTORY:]],
        }
        with open(self.stats_file, "w") as f:
            json.dump(data, f, indent=2)

    def _get_network(self, ssid: str) -> NetworkStats:
        """Get or create network stats."""
        if ssid not in self._networks:
            self._networks[ssid] = NetworkStats(ssid=ssid)
        return self._networks[ssid]

    def record_login_success(self, network: str) -> None:
        """Record a successful login."""
        ns = self._get_network(network)
        ns.login_successes += 1
        self._add_event("login_success", network)
        self._save()

    def record_login_failure(self, network: str, error: str = "") -> None:
        """Record a failed login."""
        ns = self._get_network(network)
        ns.login_failures += 1
        self._add_event("login_failure", network, error)
        self._save()

    def record_session_end(
        self, network: str, duration: float, rx_bytes: int = 0, tx_bytes: int = 0
    ) -> None:
        """Record a completed session."""
        ns = self._get_network(network)
        ns.total_uptime += duration
        ns.total_rx_bytes += rx_bytes
        ns.total_tx_bytes += tx_bytes
        self._add_event("session_end", network, f"duration={duration:.0f}s")
        self._save()

    def record_reconnect(self, network: str) -> None:
        """Record a reconnection event."""
        ns = self._get_network(network)
        ns.reconnect_count += 1
        self._add_event("reconnect", network)
        self._save()

    def _add_event(self, event_type: str, network: str = "", details: str = "") -> None:
        """Add an event to history."""
        self._history.append(ConnectionEvent(event_type, network, details))
        if len(self._history) > MAX_HISTORY:
            self._history = self._history[-MAX_HISTORY:]

    def get_network_stats(self, ssid: str) -> Optional[NetworkStats]:
        """Get stats for a specific network."""
        return self._networks.get(ssid)

    def get_all_stats(self) -> list[NetworkStats]:
        """Get stats for all networks, sorted by uptime."""
        return sorted(
            self._networks.values(),
            key=lambda s: s.total_uptime,
            reverse=True,
        )

    def get_history(self, limit: int = 20) -> list[ConnectionEvent]:
        """Get recent connection events.

        Args:
            limit: Maximum events to return.

        Returns:
            List of recent events, newest first.
        """
        return list(reversed(self._history[-limit:]))

    @property
    def total_logins(self) -> int:
        """Total successful logins across all networks."""
        return sum(ns.login_successes for ns in self._networks.values())

    @property
    def total_uptime(self) -> float:
        """Total uptime across all networks in seconds."""
        return sum(ns.total_uptime for ns in self._networks.values())

    @property
    def total_bandwidth(self) -> int:
        """Total bytes transferred across all networks."""
        return sum(
            ns.total_rx_bytes + ns.total_tx_bytes
            for ns in self._networks.values()
        )
