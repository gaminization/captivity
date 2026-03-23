"""
WiFi session uptime tracker.

Tracks the duration of each WiFi session from login to
disconnection or session expiry. Integrates with the event
bus to automatically start/stop timing.

Session data is stored in-memory and optionally persisted
to the stats database.
"""

import time
from typing import Optional

from captivity.utils.logging import get_logger

logger = get_logger("session")


class Session:
    """A single WiFi session.

    Attributes:
        network: Network SSID.
        start_time: Session start timestamp (epoch).
        end_time: Session end timestamp, or None if active.
        plugin: Plugin used for login.
    """

    def __init__(self, network: str, plugin: str = "") -> None:
        self.network = network
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.plugin = plugin

    @property
    def is_active(self) -> bool:
        """Check if this session is still active."""
        return self.end_time is None

    @property
    def duration(self) -> float:
        """Session duration in seconds."""
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def duration_str(self) -> str:
        """Human-readable session duration."""
        secs = int(self.duration)
        if secs < 60:
            return f"{secs}s"
        elif secs < 3600:
            return f"{secs // 60}m {secs % 60}s"
        else:
            hours = secs // 3600
            mins = (secs % 3600) // 60
            return f"{hours}h {mins}m"

    def end(self) -> None:
        """End this session."""
        if self.is_active:
            self.end_time = time.time()
            logger.info(
                "Session ended for '%s' (duration: %s)",
                self.network,
                self.duration_str,
            )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "network": self.network,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "plugin": self.plugin,
            "duration": self.duration,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """Deserialize from dictionary."""
        s = cls(network=data["network"], plugin=data.get("plugin", ""))
        s.start_time = data["start_time"]
        s.end_time = data.get("end_time")
        return s

    def __repr__(self) -> str:
        status = "active" if self.is_active else "ended"
        return f"Session({self.network!r}, {self.duration_str}, {status})"


class SessionTracker:
    """Tracks WiFi session lifetimes.

    Provides current session info and history of past sessions.

    Attributes:
        current: The currently active session, or None.
        history: List of completed sessions.
    """

    def __init__(self, max_history: int = 100) -> None:
        self.current: Optional[Session] = None
        self.history: list[Session] = []
        self._max_history = max_history

    def start(self, network: str, plugin: str = "") -> Session:
        """Start a new session.

        If there's an existing active session, it is ended first.

        Args:
            network: Network SSID.
            plugin: Plugin used for login.

        Returns:
            The new Session object.
        """
        if self.current and self.current.is_active:
            self.current.end()
            self._archive(self.current)

        session = Session(network=network, plugin=plugin)
        self.current = session
        logger.info("Session started for '%s'", network)
        return session

    def end(self) -> Optional[Session]:
        """End the current session.

        Returns:
            The ended session, or None if no active session.
        """
        if self.current and self.current.is_active:
            self.current.end()
            self._archive(self.current)
            ended = self.current
            self.current = None
            return ended
        return None

    def _archive(self, session: Session) -> None:
        """Archive a completed session to history."""
        self.history.append(session)
        if len(self.history) > self._max_history:
            self.history = self.history[-self._max_history:]

    @property
    def total_uptime(self) -> float:
        """Total uptime across all sessions in seconds."""
        total = sum(s.duration for s in self.history)
        if self.current and self.current.is_active:
            total += self.current.duration
        return total

    @property
    def session_count(self) -> int:
        """Total number of sessions (including current)."""
        count = len(self.history)
        if self.current:
            count += 1
        return count
