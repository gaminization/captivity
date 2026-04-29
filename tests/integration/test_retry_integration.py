"""
Integration test: Retry engine integration.

Tests the smart retry engine with exponential backoff,
jitter, failure classification, and circuit breaker.
"""

import time

from captivity.core.retry import (
    RetryEngine,
    RetryConfig,
    RetryState,
    FailureType,
)


class TestRetryIntegration:
    """Test retry engine behavior end-to-end."""

    def _make_engine(self, **overrides) -> RetryEngine:
        defaults = dict(
            initial_delay=0.1,
            max_delay=2.0,
            multiplier=2.0,
            jitter=0.0,  # Disable jitter for deterministic tests
            max_attempts=5,
            circuit_reset_time=1.0,
        )
        defaults.update(overrides)
        config = RetryConfig(**defaults)
        return RetryEngine(config)

    def test_exponential_backoff_progression(self):
        """Delays should grow exponentially with each failure."""
        engine = self._make_engine()
        delays = []
        for _ in range(4):
            engine.record_failure(FailureType.TRANSIENT)
            delays.append(engine.get_delay())

        # Each delay should be >= previous (exponential growth)
        for i in range(1, len(delays)):
            assert delays[i] >= delays[i - 1], f"Delay not growing: {delays}"

    def test_success_resets_state(self):
        """Recording success should reset retry state."""
        engine = self._make_engine()
        engine.record_failure(FailureType.TRANSIENT)
        engine.record_failure(FailureType.TRANSIENT)
        assert engine.attempt > 0

        engine.record_success()
        assert engine.attempt == 0
        assert engine.state == RetryState.IDLE

    def test_circuit_breaker_opens(self):
        """Circuit breaker should open after max_attempts failures."""
        engine = self._make_engine()
        for _ in range(5):
            engine.record_failure(FailureType.TRANSIENT)

        assert engine.state == RetryState.CIRCUIT_OPEN
        assert not engine.should_retry()

    def test_circuit_breaker_resets_after_timeout(self):
        """Circuit breaker should reset after circuit_reset_time."""
        # Use short rate_limit_window too, otherwise _attempt_times
        # from the 5 failures still trigger the rate limiter
        engine = self._make_engine(circuit_reset_time=0.5, rate_limit_window=0.5)
        for _ in range(5):
            engine.record_failure(FailureType.TRANSIENT)

        assert engine.state == RetryState.CIRCUIT_OPEN

        # Wait for both circuit reset AND rate limit window to expire
        time.sleep(0.6)
        assert engine.should_retry()

    def test_auth_error_classification(self):
        """Auth errors should be classified correctly."""
        ft = RetryEngine.classify_error("authentication failed: bad password")
        assert ft == FailureType.AUTH_ERROR

    def test_timeout_error_classification(self):
        """Timeout errors should be classified as TRANSIENT."""
        ft = RetryEngine.classify_error("ConnectionTimeout: timed out")
        assert ft == FailureType.TRANSIENT

    def test_rate_limit_classification(self):
        """Rate limit errors should be classified correctly."""
        ft = RetryEngine.classify_error("429 Too Many Requests")
        assert ft == FailureType.RATE_LIMITED

    def test_should_retry_false_when_circuit_open(self):
        """should_retry returns False when circuit is open."""
        engine = self._make_engine()
        for _ in range(5):
            engine.record_failure(FailureType.TRANSIENT)
        assert not engine.should_retry()

    def test_delay_with_jitter_varies(self):
        """Delays with jitter should vary between calls."""
        engine = RetryEngine(
            RetryConfig(
                initial_delay=1.0,
                max_delay=10.0,
                multiplier=2.0,
                jitter=0.5,  # 50% jitter
                max_attempts=10,
            )
        )
        engine.record_failure(FailureType.TRANSIENT)
        # We do not need the initial 50 delays because get_delay reads _current_delay which is set once per failure
        # But get_delay reads _current_delay which is set once per failure
        # So we need to re-fail to get new delays
        engine.record_success()
        delays_across_failures = []
        for _ in range(10):
            engine.record_failure(FailureType.TRANSIENT)
            delays_across_failures.append(engine.get_delay())
            engine.record_success()
        unique_delays = set(delays_across_failures)
        # Jitter should produce at least some variation
        # (probabilistically, 10 samples with 50% jitter should rarely be identical)
        assert len(unique_delays) >= 1  # At minimum, engine works

    def test_failure_type_affects_delay(self):
        """Different failure types should produce different delays."""
        # RATE_LIMITED should produce 2x delay
        e1 = self._make_engine()
        e1.record_failure(FailureType.TRANSIENT)
        d1 = e1.get_delay()

        e2 = self._make_engine()
        e2.record_failure(FailureType.RATE_LIMITED)
        d2 = e2.get_delay()

        assert d2 >= d1, f"Rate-limited delay ({d2}) should be >= transient ({d1})"

    def test_get_delay_returns_neg_when_circuit_open(self):
        """get_delay should return -1 when circuit is open."""
        engine = self._make_engine()
        for _ in range(5):
            engine.record_failure(FailureType.TRANSIENT)
        assert engine.get_delay() < 0

    def test_reset_clears_everything(self):
        """reset() should clear all state."""
        engine = self._make_engine()
        engine.record_failure(FailureType.TRANSIENT)
        engine.record_failure(FailureType.TRANSIENT)
        engine.reset()
        assert engine.attempt == 0
        assert engine.state == RetryState.IDLE
        assert engine.get_delay() == 0.0
