"""
Connection state machine for Captivity.

Defines explicit connection states and valid transitions.
Integrates with the event bus to publish state change events.

States:
    INIT               → Initial state on startup
    NETWORK_CONNECTED  → WiFi interface is up
    PORTAL_DETECTED    → Captive portal redirect detected
    LOGGING_IN         → Login attempt in progress
    CONNECTED          → Internet connectivity verified
    SESSION_EXPIRED    → Was connected, now portal detected again
    NETWORK_UNAVAILABLE → No network connectivity
"""

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
}


class InvalidTransition(Exception):
    """Raised when an invalid state transition is attempted."""


class ConnectionStateMachine:
    """Manages connection state with validated transitions.

    Attributes:
        state: Current connection state.
        previous_state: Previous connection state.
    """

    def __init__(
        self,
        on_transition: Optional[Callable] = None,
    ) -> None:
        self.state = ConnectionState.INIT
        self.previous_state: Optional[ConnectionState] = None
        self._on_transition = on_transition

    def transition(self, new_state: ConnectionState) -> None:
        """Transition to a new state.

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

        self.previous_state = self.state
        old_state = self.state
        self.state = new_state

        logger.info(
            "State: %s → %s", old_state.name, new_state.name,
        )

        if self._on_transition:
            self._on_transition(
                old_state=old_state,
                new_state=new_state,
            )

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

    def __repr__(self) -> str:
        return f"ConnectionStateMachine(state={self.state.name})"
