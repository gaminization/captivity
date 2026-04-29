"""
Strict state machine for Captivity connection management.

Enforces invariants:
- Every state must have an exit path
- Non-terminal states must not exceed their timeout limits
- System must converge to CONNECTED or RETRY
"""

import time
from enum import Enum, auto
from typing import Optional, Callable

from captivity.utils.logging import get_logger

logger = get_logger("state")


class ConnectionState(Enum):
    """Connection states for the autonomous daemon."""

    INIT = auto()
    PROBING = auto()
    PORTAL = auto()
    WAIT_USER = auto()
    AUTHENTICATING = auto()
    CONNECTED = auto()
    RETRY = auto()
    ERROR = auto()


# Max allowed time in each state before watchdog triggers transition
STATE_TIMEOUTS: dict[ConnectionState, float] = {
    ConnectionState.INIT: 5.0,
    ConnectionState.PROBING: 15.0,
    ConnectionState.PORTAL: 15.0,
    ConnectionState.WAIT_USER: 300.0,
    ConnectionState.AUTHENTICATING: 45.0,
    ConnectionState.CONNECTED: float("inf"),  # Terminal/stable state
    ConnectionState.RETRY: float("inf"),  # Handled by retry engine delays
    ConnectionState.ERROR: 5.0,  # Should quickly transition to retry
}

# Strict valid transitions matrix
VALID_TRANSITIONS: dict[ConnectionState, set[ConnectionState]] = {
    ConnectionState.INIT: {
        ConnectionState.PROBING,
    },
    ConnectionState.PROBING: {
        ConnectionState.PORTAL,
        ConnectionState.CONNECTED,
        ConnectionState.ERROR,
    },
    ConnectionState.PORTAL: {
        ConnectionState.WAIT_USER,
        ConnectionState.AUTHENTICATING,
        ConnectionState.ERROR,
    },
    ConnectionState.WAIT_USER: {
        ConnectionState.CONNECTED,
        ConnectionState.RETRY,
        ConnectionState.PORTAL,  # Cooldown expired, check again
    },
    ConnectionState.AUTHENTICATING: {
        ConnectionState.CONNECTED,
        ConnectionState.RETRY,
        ConnectionState.ERROR,
        ConnectionState.WAIT_USER,  # Added for CAPTCHA fallback during login
    },
    ConnectionState.CONNECTED: {
        ConnectionState.PROBING,
    },
    ConnectionState.RETRY: {
        ConnectionState.PROBING,
        ConnectionState.AUTHENTICATING,
    },
    ConnectionState.ERROR: {
        ConnectionState.RETRY,
    },
}


MIN_STATE_DURATION = 3.0


class InvalidTransition(Exception):
    """Raised when an invalid state transition is attempted."""


class StateWatchdogViolation(Exception):
    """Raised when a state exceeds its maximum allowed duration."""


class ConnectionStateMachine:
    """Manages connection state with strict transition validation and watchdogs."""

    def __init__(
        self,
        on_transition: Optional[Callable] = None,
        debounce_duration: float = MIN_STATE_DURATION,
    ):
        self.state = ConnectionState.INIT
        self.state_entered_at: float = time.time()
        self._on_transition = on_transition
        self.debounce_duration = debounce_duration

    def force_transition(self, new_state: ConnectionState) -> None:
        """Force a transition to a new state regardless of invariants or debouncing."""
        if new_state == self.state:
            return

        now = time.time()
        duration = now - self.state_entered_at
        old_state = self.state

        logger.info(
            "STATE_TRANSITION EVENT=FORCED_TRANSITION OLD_STATE=%s NEW_STATE=%s DURATION=%.1fs",
            old_state.name,
            new_state.name,
            duration,
        )

        self.state = new_state
        self.state_entered_at = now

        if self._on_transition:
            try:
                self._on_transition(old_state=old_state, new_state=new_state)
            except Exception as e:
                logger.error("Transition callback failed: %s", e)

    def transition(self, new_state: ConnectionState) -> None:
        """Transition to a new state if valid and debounced."""
        if new_state == self.state:
            return

        now = time.time()
        duration = now - self.state_entered_at

        # Anti-oscillation debouncing
        if duration < self.debounce_duration and self.state != ConnectionState.INIT:
            logger.debug(
                "DEBOUNCE IGNORING TRANSITION: %s -> %s (duration %.1fs < %.1fs)",
                self.state.name,
                new_state.name,
                duration,
                self.debounce_duration,
            )
            return

        allowed = VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            # Force recovery on illegal state transitions to prevent deadlocks
            logger.error(
                "ILLEGAL TRANSITION: %s -> %s. Forcing ERROR state.",
                self.state.name,
                new_state.name,
            )
            self.force_transition(ConnectionState.ERROR)
            return

        old_state = self.state

        logger.info(
            "STATE_TRANSITION EVENT=TRANSITION OLD_STATE=%s NEW_STATE=%s DURATION=%.1fs",
            old_state.name,
            new_state.name,
            duration,
        )

        self.state = new_state
        self.state_entered_at = now

        if self._on_transition:
            try:
                self._on_transition(old_state=old_state, new_state=new_state)
            except Exception as e:
                logger.error("Transition callback failed: %s", e)

    def check_watchdog(self) -> None:
        """Enforce invariants. Should be called periodically by the main loop.

        If a state exceeds its timeout, it forces a transition to recover.
        """
        duration = time.time() - self.state_entered_at
        limit = STATE_TIMEOUTS.get(self.state, float("inf"))

        if duration > limit:
            logger.error(
                "WATCHDOG_VIOLATION STATE=%s DURATION=%.1fs LIMIT=%.1fs",
                self.state.name,
                duration,
                limit,
            )
            # Force recovery
            if self.state in (
                ConnectionState.PROBING,
                ConnectionState.PORTAL,
                ConnectionState.AUTHENTICATING,
            ):
                self.transition(ConnectionState.ERROR)
            elif self.state == ConnectionState.WAIT_USER:
                self.transition(ConnectionState.RETRY)
            elif self.state == ConnectionState.ERROR:
                self.transition(ConnectionState.RETRY)
            elif self.state == ConnectionState.INIT:
                self.transition(ConnectionState.PROBING)

    @property
    def is_connected(self) -> bool:
        return self.state == ConnectionState.CONNECTED
