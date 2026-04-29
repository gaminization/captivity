"""
Smart retry engine with adaptive intervals.

Provides intelligent retry logic for login attempts:
  - Exponential backoff with jitter
  - Rate limiting to prevent portal lockouts
  - Failure pattern detection (persistent vs transient)
  - Configurable backoff parameters
  - Circuit breaker to stop retrying after repeated failures

Designed for integration with the daemon runner and
event bus for automatic retry on session expiry.
"""

import random
import time
from enum import Enum
from typing import Optional

from captivity.utils.logging import get_logger

logger = get_logger("retry")


class FailureType(Enum):
    """Classification of login failures."""

    TRANSIENT = "transient"  # Network timeout, DNS failure
    AUTH_ERROR = "auth_error"  # Bad credentials
    RATE_LIMITED = "rate_limited"  # Portal rate limiting
    PORTAL_DOWN = "portal_down"  # Portal unreachable
    UNKNOWN = "unknown"


class RetryState(Enum):
    """Current state of the retry engine."""

    IDLE = "idle"
    WAITING = "waiting"
    READY = "ready"
    CIRCUIT_OPEN = "circuit_open"  # Stop retrying


class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        initial_delay: First retry delay in seconds.
        max_delay: Maximum retry delay in seconds.
        multiplier: Backoff multiplier.
        jitter: Maximum jitter factor (0.0 to 1.0).
        max_attempts: Max consecutive failures before circuit opens.
        rate_limit_window: Window for rate limiting (seconds).
        rate_limit_max: Max attempts within the rate limit window.
        circuit_reset_time: Time to wait before resetting circuit breaker.
    """

    def __init__(
        self,
        initial_delay: float = 5.0,
        max_delay: float = 300.0,
        multiplier: float = 2.0,
        jitter: float = 0.25,
        max_attempts: int = 10,
        rate_limit_window: float = 60.0,
        rate_limit_max: int = 5,
        circuit_reset_time: float = 600.0,
    ) -> None:
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.jitter = jitter
        self.max_attempts = max_attempts
        self.rate_limit_window = rate_limit_window
        self.rate_limit_max = rate_limit_max
        self.circuit_reset_time = circuit_reset_time


class RetryEngine:
    """Smart retry engine with adaptive backoff.

    Tracks login attempts, classifies failures, and computes
    optimal retry delays. Includes a circuit breaker that
    stops retrying after repeated failures.

    Attributes:
        config: Retry configuration.
        state: Current retry state.
        attempt: Current consecutive failure count.
    """

    def __init__(self, config: Optional[RetryConfig] = None) -> None:
        self.config = config or RetryConfig()
        self._state = RetryState.IDLE
        self._attempt = 0
        self._last_failure_type: Optional[FailureType] = None
        self._attempt_times: list[float] = []
        self._circuit_opened_at: Optional[float] = None
        self._current_delay: float = self.config.initial_delay

    @property
    def state(self) -> RetryState:
        """Current retry state, with circuit breaker auto-reset."""
        if self._state == RetryState.CIRCUIT_OPEN:
            if (
                self._circuit_opened_at
                and time.time() - self._circuit_opened_at
                >= self.config.circuit_reset_time
            ):
                logger.info(
                    "Circuit breaker reset after %.0fs", self.config.circuit_reset_time
                )
                self.reset()
                return RetryState.IDLE
        return self._state

    @property
    def attempt(self) -> int:
        """Current consecutive failure count."""
        return self._attempt

    @property
    def last_failure_type(self) -> Optional[FailureType]:
        """Type of the most recent failure."""
        return self._last_failure_type

    def record_success(self) -> None:
        """Record a successful login. Resets all counters."""
        logger.info("Login succeeded, resetting retry state")
        self.reset()

    def record_failure(self, failure_type: FailureType = FailureType.UNKNOWN) -> None:
        """Record a failed login attempt.

        Args:
            failure_type: Classification of the failure.
        """
        self._attempt += 1
        self._last_failure_type = failure_type
        self._attempt_times.append(time.time())
        self._prune_attempt_times()

        # Auth errors should not trigger repeated retries
        if failure_type == FailureType.AUTH_ERROR:
            logger.warning("Auth error — opening circuit breaker")
            self._open_circuit()
            return

        # Check circuit breaker threshold
        if self._attempt >= self.config.max_attempts:
            logger.warning(
                "Max attempts (%d) reached — opening circuit breaker",
                self.config.max_attempts,
            )
            self._open_circuit()
            return

        # Compute next delay
        self._current_delay = self._compute_delay()
        self._state = RetryState.WAITING

        logger.info(
            "Attempt %d failed (%s). Next retry in %.1fs",
            self._attempt,
            failure_type.value,
            self._current_delay,
        )

    def get_delay(self) -> float:
        """Get the delay before the next retry attempt.

        Returns:
            Delay in seconds. Returns 0 if ready or idle.
            Returns -1 if circuit is open.
        """
        state = self.state  # Triggers auto-reset check
        if state == RetryState.CIRCUIT_OPEN:
            return -1.0
        if state in (RetryState.IDLE, RetryState.READY):
            return 0.0
        return self._current_delay

    def should_retry(self) -> bool:
        """Check if a retry should be attempted.

        Returns:
            True if retry is allowed.
        """
        state = self.state
        if state == RetryState.CIRCUIT_OPEN:
            return False
        if self._is_rate_limited():
            logger.debug("Rate limited — too many attempts in window")
            return False
        return True

    def mark_ready(self) -> None:
        """Mark the engine as ready for the next attempt.

        Called after the delay period has elapsed.
        """
        if self._state == RetryState.WAITING:
            self._state = RetryState.READY

    def reset(self) -> None:
        """Reset all retry state."""
        self._state = RetryState.IDLE
        self._attempt = 0
        self._last_failure_type = None
        self._current_delay = self.config.initial_delay
        self._circuit_opened_at = None

    def _compute_delay(self) -> float:
        """Compute the next retry delay with jitter.

        Uses exponential backoff with additive jitter,
        modulated by failure type:
          - TRANSIENT: normal backoff
          - RATE_LIMITED: 2x backoff (respect portal limits)
          - PORTAL_DOWN: 3x backoff (portal may be down)
        """
        base = self.config.initial_delay * (
            self.config.multiplier ** (self._attempt - 1)
        )

        # Modulate by failure type
        if self._last_failure_type == FailureType.RATE_LIMITED:
            base *= 2.0
        elif self._last_failure_type == FailureType.PORTAL_DOWN:
            base *= 3.0

        # Clamp to max
        base = min(base, self.config.max_delay)

        # Add jitter
        jitter = base * self.config.jitter * random.random()
        return base + jitter

    def _is_rate_limited(self) -> bool:
        """Check if we're making too many attempts too quickly."""
        self._prune_attempt_times()
        return len(self._attempt_times) >= self.config.rate_limit_max

    def _prune_attempt_times(self) -> None:
        """Remove attempt times outside the rate limit window."""
        cutoff = time.time() - self.config.rate_limit_window
        self._attempt_times = [t for t in self._attempt_times if t > cutoff]

    def _open_circuit(self) -> None:
        """Open the circuit breaker."""
        self._state = RetryState.CIRCUIT_OPEN
        self._circuit_opened_at = time.time()

    @classmethod
    def classify_error(cls, error: str) -> FailureType:
        """Classify an error string into a FailureType.

        Args:
            error: Error message or exception string.

        Returns:
            Classified FailureType.
        """
        error_lower = error.lower()

        if any(
            kw in error_lower
            for kw in ("timeout", "dns", "resolve", "connection reset")
        ):
            return FailureType.TRANSIENT
        if any(
            kw in error_lower for kw in ("401", "403", "invalid credentials", "auth")
        ):
            return FailureType.AUTH_ERROR
        if any(kw in error_lower for kw in ("429", "rate limit", "too many")):
            return FailureType.RATE_LIMITED
        if any(kw in error_lower for kw in ("503", "502", "unreachable", "refused")):
            return FailureType.PORTAL_DOWN

        return FailureType.UNKNOWN
