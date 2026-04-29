"""
JSON API endpoints for the web dashboard.

Provides structured data from the telemetry and profile
subsystems for consumption by the dashboard frontend.

All endpoints return JSON. No authentication required
since the server only binds to localhost.
"""

import json
import time
from typing import Any, Optional

from captivity.utils.logging import get_logger

logger = get_logger("dashboard.api")


class DashboardAPI:
    """Provides JSON data for dashboard endpoints.

    Aggregates data from telemetry, profiles, and daemon
    state into structured API responses.

    Attributes:
        stats_db: Optional StatsDatabase instance.
        profile_db: Optional ProfileDatabase instance.
        session_tracker: Optional SessionTracker instance.
        bandwidth_monitor: Optional BandwidthMonitor instance.
    """

    def __init__(
        self,
        stats_db: Any = None,
        profile_db: Any = None,
        session_tracker: Any = None,
        bandwidth_monitor: Any = None,
    ) -> None:
        self.stats_db = stats_db
        self.profile_db = profile_db
        self.session_tracker = session_tracker
        self.bandwidth_monitor = bandwidth_monitor

    def _lazy_load(self) -> None:
        """Lazy-load databases if not provided."""
        if self.stats_db is None:
            try:
                from captivity.telemetry.stats import StatsDatabase

                self.stats_db = StatsDatabase()
            except Exception:
                pass

        if self.profile_db is None:
            try:
                from captivity.core.profiles import ProfileDatabase

                self.profile_db = ProfileDatabase()
            except Exception:
                pass

    def get_status(self) -> dict:
        """Get current connection status.

        Returns:
            Dict with state, network, uptime, daemon info.
        """
        self._lazy_load()

        result = {
            "state": "unknown",
            "network": "",
            "uptime": 0,
            "uptime_str": "",
            "timestamp": time.time(),
        }

        if self.session_tracker and self.session_tracker.current:
            session = self.session_tracker.current
            result["state"] = "connected"
            result["network"] = session.network
            result["uptime"] = session.duration
            result["uptime_str"] = session.duration_str
        else:
            result["state"] = "idle"

        return result

    def get_stats(self) -> dict:
        """Get aggregated statistics.

        Returns:
            Dict with total logins, uptime, bandwidth, per-network stats.
        """
        self._lazy_load()

        if not self.stats_db:
            return {
                "total_logins": 0,
                "total_uptime": 0,
                "total_bandwidth": 0,
                "networks": [],
            }

        networks = []
        for ns in self.stats_db.get_all_stats():
            networks.append(
                {
                    "ssid": ns.ssid,
                    "login_successes": ns.login_successes,
                    "login_failures": ns.login_failures,
                    "success_rate": round(ns.success_rate * 100, 1),
                    "total_uptime": round(ns.total_uptime, 1),
                    "total_rx_bytes": ns.total_rx_bytes,
                    "total_tx_bytes": ns.total_tx_bytes,
                    "reconnect_count": ns.reconnect_count,
                }
            )

        return {
            "total_logins": self.stats_db.total_logins,
            "total_uptime": round(self.stats_db.total_uptime, 1),
            "total_bandwidth": self.stats_db.total_bandwidth,
            "networks": networks,
        }

    def get_history(self, limit: int = 30) -> list[dict]:
        """Get recent connection events.

        Args:
            limit: Maximum events to return.

        Returns:
            List of event dicts, newest first.
        """
        self._lazy_load()

        if not self.stats_db:
            return []

        events = self.stats_db.get_history(limit=limit)
        return [
            {
                "timestamp": e.timestamp,
                "time_str": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(e.timestamp)
                ),
                "event_type": e.event_type,
                "network": e.network,
                "details": e.details,
            }
            for e in events
        ]

    def get_networks(self) -> list[dict]:
        """Get known network profiles.

        Returns:
            List of network profile dicts.
        """
        self._lazy_load()

        if not self.profile_db:
            return []

        return [
            {
                "ssid": p.ssid,
                "plugin": p.plugin_name,
                "login_count": p.login_count,
                "has_portal_info": p.has_portal_info,
                "portal_domain": p.fingerprint.portal_domain,
                "gateway_ip": p.fingerprint.gateway_ip,
            }
            for p in self.profile_db.list_profiles()
        ]

    def get_bandwidth(self) -> dict:
        """Get current bandwidth usage.

        Returns:
            Dict with interface, session usage, current stats.
        """
        result = {"interface": "", "session": None, "current": None}

        if not self.bandwidth_monitor:
            return result

        result["interface"] = self.bandwidth_monitor.interface

        usage = self.bandwidth_monitor.get_session_usage()
        if usage:
            result["session"] = {
                "rx_bytes": usage.rx_bytes,
                "tx_bytes": usage.tx_bytes,
                "total_bytes": usage.total_bytes,
            }

        current = self.bandwidth_monitor.get_current_stats()
        if current:
            result["current"] = {
                "rx_bytes": current.rx_bytes,
                "tx_bytes": current.tx_bytes,
                "total_bytes": current.total_bytes,
            }

        return result

    def handle_request(self, path: str) -> Optional[str]:
        """Route an API request path to the correct handler.

        Args:
            path: URL path (e.g. '/api/status').

        Returns:
            JSON string, or None if path not found.
        """
        routes = {
            "/api/status": self.get_status,
            "/api/stats": self.get_stats,
            "/api/history": self.get_history,
            "/api/networks": self.get_networks,
            "/api/bandwidth": self.get_bandwidth,
        }

        handler = routes.get(path)
        if handler:
            try:
                data = handler()
                return json.dumps(data, indent=2)
            except Exception as exc:
                logger.error("API error for %s: %s", path, exc)
                return json.dumps({"error": str(exc)})

        return None
