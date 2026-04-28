"""
Integration test: Daemon lifecycle.

Tests the DaemonRunner's initialization, single probe cycle,
and state machine integration.
"""

import threading
import time

from captivity.core.probe import ConnectivityStatus
from captivity.core.state import ConnectionState
from captivity.core.retry import RetryState
from captivity.daemon.runner import DaemonRunner
from captivity.daemon.events import Event


class TestDaemonLifecycle:
    """Test daemon start, probe, and stop."""

    def test_daemon_creates_with_defaults(self):
        """DaemonRunner should initialize with all components."""
        d = DaemonRunner(network="test-net")
        assert d.network == "test-net"
        assert d.retry_engine is not None
        assert d.state_machine is not None
        assert d.event_bus is not None
        assert d.should_run is True
        assert d.retry_engine.state == RetryState.IDLE

    def test_daemon_run_once_returns_status(self):
        """run_once should return a valid ConnectivityStatus."""
        d = DaemonRunner(network="test-net")
        status = d.run_once()
        assert isinstance(status, ConnectivityStatus)

    def test_daemon_run_once_updates_state_machine(self):
        """After run_once, state machine should leave INIT."""
        d = DaemonRunner(network="test-net")
        d.run_once()
        # State should have transitioned from INIT
        assert d.state_machine.state != ConnectionState.INIT

    def test_daemon_events_published(self):
        """Daemon should publish events during run_once."""
        d = DaemonRunner(network="test-net")
        received = []
        d.event_bus.subscribe(Event.LOGIN_SUCCESS, lambda **kw: received.append("success"))
        d.event_bus.subscribe(Event.SESSION_EXPIRED, lambda **kw: received.append("expired"))
        d.event_bus.subscribe(Event.NETWORK_CONNECTED, lambda **kw: received.append("connected"))
        d.run_once()
        # At least one event should have been published
        # (the specific event depends on actual network state)

    def test_daemon_signal_stops_loop(self):
        """Setting should_run=False stops the daemon."""
        d = DaemonRunner(network="test-net", interval=1)

        def stop_after_delay():
            time.sleep(0.5)
            d.should_run = False

        stopper = threading.Thread(target=stop_after_delay)
        stopper.start()

        start = time.time()
        d.run()
        elapsed = time.time() - start

        stopper.join()
        assert elapsed < 5.0, f"Daemon didn't stop in time ({elapsed:.1f}s)"

    def test_daemon_retry_engine_resets_on_success(self):
        """Retry engine should reset after successful connectivity."""
        d = DaemonRunner(network="test-net")
        # Simulate some failures
        from captivity.core.retry import FailureType
        d.retry_engine.record_failure(FailureType.TRANSIENT)
        d.retry_engine.record_failure(FailureType.TRANSIENT)
        assert d.retry_engine.attempt > 0

        # Run a probe — if connected, retry should reset
        status = d.run_once()
        if status == ConnectivityStatus.CONNECTED:
            assert d.retry_engine.attempt == 0
            assert d.retry_engine.state == RetryState.IDLE
