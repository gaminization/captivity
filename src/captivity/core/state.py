"""
Connection state machine for Captivity.

Defines explicit connection states and valid transitions.
Integrates with the event bus and retry engine.

States:
    INIT               → Initial state on startup
    NETWORK_CONNECTED  → WiFi interface is up
    PORTAL_DETECTED    → Captive portal redirect detected
    LOGGING_IN         → Login attempt in progress
    CONNECTED          → Internet connectivity verified
    SESSION_EXPIRED    → Was connected, now portal detected again
    NETWORK_UNAVAILABLE → No network connectivity
    RETRY_WAIT         → Waiting for retry delay to elapse

Enhanced in v1.6:
    - Transition history tracking (capped at 100)
    - State duration measurement
    - RetryEngine integration
    - Event bus auto-publishing
"""

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

from captivity.utils.logging import get_logger

logger = get_logger("state")


class ConnectionState(Enum):
    """Connection states for the daemon."""
    INIT = auto()
    NETWORK_CONNECTED = auto()
    PORTAL_DETECTED = auto()
    LOGGING_IN = auto()
    CONNECTED = auto()
    SESSION_EXPIRED = auto()
    NETWORK_UNAVAILABLE = auto()
    RETRY_WAIT = auto()


# Valid state transitions: current_state → set of allowed next states
VALID_TRANSITIONS: dict[ConnectionState, set[ConnectionState]] = {
    ConnectionState.INIT: {
        ConnectionState.NETWORK_CONNECTED,
        ConnectionState.NETWORK_UNAVAILABLE,
        ConnectionState.PORTAL_DETECTED,
        ConnectionState.CONNECTED,
    },
    ConnectionState.NETWORK_CONNECTED: {
        ConnectionState.PORTAL_DETECTED,
        ConnectionState.CONNECTED,
        ConnectionState.NETWORK_UNAVAILABLE,
    },
    ConnectionState.PORTAL_DETECTED: {
        ConnectionState.LOGGING_IN,
        ConnectionState.NETWORK_UNAVAILABLE,
    },
    ConnectionState.LOGGING_IN: {
        ConnectionState.CONNECTED,
        ConnectionState.PORTAL_DETECTED,  # login failed, retry
        ConnectionState.NETWORK_UNAVAILABLE,
        ConnectionState.RETRY_WAIT,  # waiting for retry delay
    },
    ConnectionState.CONNECTED: {
        ConnectionState.SESSION_EXPIRED,
        ConnectionState.NETWORK_UNAVAILABLE,
        ConnectionState.PORTAL_DETECTED,
    },
    ConnectionState.SESSION_EXPIRED: {
        ConnectionState.PORTAL_DETECTED,
        ConnectionState.NETWORK_UNAVAILABLE,
        ConnectionState.CONNECTED,
    },
    ConnectionState.NETWORK_UNAVAILABLE: {
        ConnectionState.NETWORK_CONNECTED,
        ConnectionState.PORTAL_DETECTED,
        ConnectionState.CONNECTED,
    },
    ConnectionState.RETRY_WAIT: {
        ConnectionState.LOGGING_IN,  # retry timer elapsed
        ConnectionState.PORTAL_DETECTED,
        ConnectionState.NETWORK_UNAVAILABLE,
        ConnectionState.CONNECTED,  # connectivity recovered
    },
}


class InvalidTransition(Exception):
    """Raised when an invalid state transition is attempted."""


@dataclass
class TransitionRecord:
    """Record of a single state transition.

    Attributes:
        from_state: Source state.
        to_state: Destination state.
        timestamp: Time of transition.
        duration: Time spent in the source state (seconds).
    """
    from_state: ConnectionState
    to_state: ConnectionState
    timestamp: float = field(default_factory=time.time)
    duration: float = 0.0


class ConnectionStateMachine:
    """Manages connection state with validated transitions.

    Enhanced in v1.6 with transition history, state duration
    tracking, retry engine integration, and event bus publishing.

    Attributes:
        state: Current connection state.
        previous_state: Previous connection state.
        history: List of recent transitions (max 100).
        state_entered_at: Timestamp when current state was entered.
    """

    MAX_HISTORY = 100

    def __init__(
        self,
        on_transition: Optional[Callable] = None,
        retry_engine: Optional[object] = None,
        event_bus: Optional[object] = None,
    ) -> None:
        self.state = ConnectionState.INIT
        self.previous_state: Optional[ConnectionState] = None
        self.state_entered_at: float = time.time()
        self.history: list[TransitionRecord] = []
        self._on_transition = on_transition
        self._retry_engine = retry_engine
        self._event_bus = event_bus

    def transition(self, new_state: ConnectionState) -> None:
        """Transition to a new state.

        Records transition history, publishes events, and
        integrates with the retry engine.

        Args:
            new_state: The target state.

        Raises:
            InvalidTransition: If the transition is not valid.
        """
        if new_state == self.state:
            return  # No-op for same-state

        allowed = VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise InvalidTransition(
                f"Cannot transition from {self.state.name} to {new_state.name}"
            )

        now = time.time()
        duration = now - self.state_entered_at

        # Record transition
        record = TransitionRecord(
            from_state=self.state,
            to_state=new_state,
            timestamp=now,
            duration=duration,
        )
        self.history.append(record)
        if len(self.history) > self.MAX_HISTORY:
            self.history = self.history[-self.MAX_HISTORY:]

        self.previous_state = self.state
        old_state = self.state
        self.state = new_state
        self.state_entered_at = now

        logger.info(
            "State: %s → %s (%.1fs in %s)",
            old_state.name, new_state.name, duration, old_state.name,
        )

        # Retry engine integration
        self._handle_retry_integration(old_state, new_state)

        # Event bus publishing
        self._publish_event(old_state, new_state)

        # Custom callback
        if self._on_transition:
            self._on_transition(
                old_state=old_state,
                new_state=new_state,
            )

    def _handle_retry_integration(
        self, old_state: ConnectionState, new_state: ConnectionState,
    ) -> None:
        """Integrate retry engine with state transitions."""
        if not self._retry_engine:
            return

        if new_state == ConnectionState.CONNECTED:
            self._retry_engine.record_success()
        elif (old_state == ConnectionState.LOGGING_IN and
              new_state in (ConnectionState.PORTAL_DETECTED,
                            ConnectionState.RETRY_WAIT)):
            from captivity.core.retry import FailureType
            self._retry_engine.record_failure(FailureType.TRANSIENT)

    def _publish_event(
        self, old_state: ConnectionState, new_state: ConnectionState,
    ) -> None:
        """Publish state change events to the event bus."""
        if not self._event_bus:
            return

        # Map state transitions to event names
        event_map = {
            ConnectionState.NETWORK_CONNECTED: "NETWORK_CONNECTED",
            ConnectionState.PORTAL_DETECTED: "PORTAL_DETECTED",
            ConnectionState.CONNECTED: "LOGIN_SUCCESS",
            ConnectionState.SESSION_EXPIRED: "SESSION_EXPIRED",
            ConnectionState.NETWORK_UNAVAILABLE: "NETWORK_DISCONNECTED",
        }

        event = event_map.get(new_state)
        if event and hasattr(self._event_bus, "publish"):
            try:
                self._event_bus.publish(event)
            except Exception as exc:
                logger.debug("Event publish failed: %s", exc)

    @property
    def is_connected(self) -> bool:
        """Whether currently connected to internet."""
        return self.state == ConnectionState.CONNECTED

    @property
    def needs_login(self) -> bool:
        """Whether a login attempt is needed."""
        return self.state in (
            ConnectionState.PORTAL_DETECTED,
            ConnectionState.SESSION_EXPIRED,
        )

    @property
    def is_waiting(self) -> bool:
        """Whether waiting for retry delay."""
        return self.state == ConnectionState.RETRY_WAIT

    @property
    def state_duration(self) -> float:
        """Time spent in current state (seconds)."""
        return time.time() - self.state_entered_at

    @property
    def transition_count(self) -> int:
        """Total number of recorded transitions."""
        return len(self.history)

    def get_state_stats(self) -> dict[str, float]:
        """Get total time spent in each state.

        Returns:
            Dict mapping state name to total seconds.
        """
        stats: dict[str, float] = {s.name: 0.0 for s in ConnectionState}
        for record in self.history:
            stats[record.from_state.name] += record.duration
        # Add current state duration
        stats[self.state.name] += self.state_duration
        return stats

    def __repr__(self) -> str:
        return f"ConnectionStateMachine(state={self.state.name})"

