"""Tests for captivity.core.retry module."""

import time
import unittest

from captivity.core.retry import (
    FailureType,
    RetryConfig,
    RetryEngine,
    RetryState,
)


class TestRetryConfig(unittest.TestCase):
    """Test RetryConfig defaults."""

    def test_defaults(self):
        c = RetryConfig()
        self.assertEqual(c.initial_delay, 5.0)
        self.assertEqual(c.max_delay, 300.0)
        self.assertEqual(c.multiplier, 2.0)
        self.assertEqual(c.max_attempts, 10)

    def test_custom(self):
        c = RetryConfig(initial_delay=1.0, max_delay=60.0)
        self.assertEqual(c.initial_delay, 1.0)
        self.assertEqual(c.max_delay, 60.0)


class TestRetryEngine(unittest.TestCase):
    """Test RetryEngine core behavior."""

    def test_initial_state(self):
        e = RetryEngine()
        self.assertEqual(e.state, RetryState.IDLE)
        self.assertEqual(e.attempt, 0)
        self.assertTrue(e.should_retry())

    def test_record_success_resets(self):
        e = RetryEngine()
        e.record_failure(FailureType.TRANSIENT)
        e.record_success()
        self.assertEqual(e.state, RetryState.IDLE)
        self.assertEqual(e.attempt, 0)

    def test_record_failure_increments(self):
        e = RetryEngine()
        e.record_failure(FailureType.TRANSIENT)
        self.assertEqual(e.attempt, 1)
        self.assertEqual(e.state, RetryState.WAITING)
        self.assertEqual(e.last_failure_type, FailureType.TRANSIENT)

    def test_exponential_backoff(self):
        config = RetryConfig(initial_delay=1.0, multiplier=2.0, jitter=0.0)
        e = RetryEngine(config=config)
        e.record_failure(FailureType.TRANSIENT)
        delay1 = e.get_delay()
        e.mark_ready()
        e.record_failure(FailureType.TRANSIENT)
        delay2 = e.get_delay()
        self.assertGreater(delay2, delay1)

    def test_max_delay_cap(self):
        config = RetryConfig(initial_delay=100.0, max_delay=200.0, jitter=0.0)
        e = RetryEngine(config=config)
        for _ in range(10):
            if e.state == RetryState.CIRCUIT_OPEN:
                break
            e.record_failure(FailureType.TRANSIENT)
        # All delays should be <= max_delay + jitter
        self.assertLessEqual(e.get_delay(), 200.0 * 1.25 + 1)

    def test_auth_error_opens_circuit(self):
        e = RetryEngine()
        e.record_failure(FailureType.AUTH_ERROR)
        self.assertEqual(e.state, RetryState.CIRCUIT_OPEN)
        self.assertFalse(e.should_retry())

    def test_circuit_breaker_after_max_attempts(self):
        config = RetryConfig(max_attempts=3)
        e = RetryEngine(config=config)
        for _ in range(3):
            e.record_failure(FailureType.TRANSIENT)
        self.assertEqual(e.state, RetryState.CIRCUIT_OPEN)

    def test_circuit_auto_reset(self):
        config = RetryConfig(max_attempts=2, circuit_reset_time=0.1)
        e = RetryEngine(config=config)
        e.record_failure(FailureType.TRANSIENT)
        e.record_failure(FailureType.TRANSIENT)
        self.assertEqual(e.state, RetryState.CIRCUIT_OPEN)
        time.sleep(0.15)
        self.assertEqual(e.state, RetryState.IDLE)

    def test_mark_ready(self):
        e = RetryEngine()
        e.record_failure(FailureType.TRANSIENT)
        self.assertEqual(e.state, RetryState.WAITING)
        e.mark_ready()
        self.assertEqual(e.state, RetryState.READY)

    def test_rate_limiting(self):
        config = RetryConfig(
            rate_limit_window=60.0,
            rate_limit_max=3,
            max_attempts=20,
        )
        e = RetryEngine(config=config)
        for _ in range(3):
            e.record_failure(FailureType.TRANSIENT)
        self.assertFalse(e.should_retry())

    def test_get_delay_idle(self):
        e = RetryEngine()
        self.assertEqual(e.get_delay(), 0.0)

    def test_get_delay_circuit_open(self):
        e = RetryEngine()
        e.record_failure(FailureType.AUTH_ERROR)
        self.assertEqual(e.get_delay(), -1.0)

    def test_reset(self):
        e = RetryEngine()
        e.record_failure(FailureType.TRANSIENT)
        e.record_failure(FailureType.TRANSIENT)
        e.reset()
        self.assertEqual(e.state, RetryState.IDLE)
        self.assertEqual(e.attempt, 0)

    def test_rate_limited_failures_increase_delay(self):
        config = RetryConfig(initial_delay=1.0, jitter=0.0, max_attempts=20)
        e = RetryEngine(config=config)
        e.record_failure(FailureType.TRANSIENT)
        transient_delay = e.get_delay()
        e.reset()
        e.record_failure(FailureType.RATE_LIMITED)
        rl_delay = e.get_delay()
        self.assertGreater(rl_delay, transient_delay)

    def test_portal_down_largest_delay(self):
        config = RetryConfig(initial_delay=1.0, jitter=0.0, max_attempts=20)
        e = RetryEngine(config=config)
        e.record_failure(FailureType.PORTAL_DOWN)
        pd_delay = e.get_delay()
        e.reset()
        e.record_failure(FailureType.RATE_LIMITED)
        rl_delay = e.get_delay()
        self.assertGreater(pd_delay, rl_delay)


class TestClassifyError(unittest.TestCase):
    """Test error classification."""

    def test_timeout(self):
        self.assertEqual(
            RetryEngine.classify_error("Connection timeout"), FailureType.TRANSIENT
        )

    def test_dns(self):
        self.assertEqual(
            RetryEngine.classify_error("DNS resolve failure"), FailureType.TRANSIENT
        )

    def test_auth(self):
        self.assertEqual(
            RetryEngine.classify_error("HTTP 401 Unauthorized"), FailureType.AUTH_ERROR
        )

    def test_rate_limit(self):
        self.assertEqual(
            RetryEngine.classify_error("429 Too Many Requests"),
            FailureType.RATE_LIMITED,
        )

    def test_portal_down(self):
        self.assertEqual(
            RetryEngine.classify_error("503 Service Unavailable"),
            FailureType.PORTAL_DOWN,
        )

    def test_unknown(self):
        self.assertEqual(
            RetryEngine.classify_error("Something happened"), FailureType.UNKNOWN
        )

    def test_connection_refused(self):
        self.assertEqual(
            RetryEngine.classify_error("Connection refused"), FailureType.PORTAL_DOWN
        )


if __name__ == "__main__":
    unittest.main()
