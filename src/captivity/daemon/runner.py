"""
Event-driven, failure-proof daemon runner.

Integrates the strict state machine, dual-layer network monitor,
and smart retry engine to handle captive portal logins autonomously.

Guarantees:
  - Eventual consistency (reconciliation loop)
  - No stuck states (state watchdogs)
  - Crash resilience (recovery loops)
  - Startup reconciliation window (survives boot-time event loss)
"""


import signal
import time
from typing import Optional

from captivity.core.probe import probe_connectivity_detailed, ConnectivityStatus
from captivity.core.login import do_login, LoginResult
from captivity.core.state import (
    ConnectionState,
    ConnectionStateMachine,
    InvalidTransition,
)
from captivity.core.retry import RetryEngine, RetryConfig, FailureType
from captivity.daemon.events import Event, EventBus
from captivity.daemon.network_monitor import NetworkMonitor, NetworkEvent
from captivity.telemetry.stats import StatsDatabase
from captivity.telemetry.session import SessionTracker
from captivity.utils.logging import get_logger
import sys

# Startup reconciliation: probe aggressively for this many seconds
# after daemon initialisation, regardless of event delivery.
STARTUP_RECONCILIATION_WINDOW = 60  # seconds
STARTUP_RECONCILIATION_INTERVAL = 5  # probe every N seconds during window

logger = get_logger("daemon")


class FaultTracker:
    """Tracks daemon crashes and controls exponential backoff and fatal shutdown."""

    def __init__(
        self, max_crashes_per_window: int = 5, window_seconds: float = 300.0
    ) -> None:
        self.crash_timestamps: list[float] = []
        self.max_crashes = max_crashes_per_window
        self.window_seconds = window_seconds
        self.base_delay = 5.0
        self.max_delay = 60.0

    def record_crash(self) -> float:
        """Records a crash and returns the recommended sleep duration. Raises SystemExit if fatal."""
        now = time.time()
        # Clean up old crashes outside the window
        self.crash_timestamps = [
            t for t in self.crash_timestamps if now - t <= self.window_seconds
        ]
        self.crash_timestamps.append(now)

        if len(self.crash_timestamps) > self.max_crashes:
            logger.critical(
                "Fatal crash limit exceeded",
                extra={
                    "crashes": len(self.crash_timestamps),
                    "window": self.window_seconds,
                },
            )
            sys.exit(1)

        # Exponential backoff based on number of recent crashes
        delay = min(
            self.max_delay, self.base_delay * (2 ** (len(self.crash_timestamps) - 1))
        )
        return delay


class DaemonRunner:
    """Autonomous event-driven reconnect daemon."""

    def __init__(
        self,
        network: Optional[str] = None,
        portal_url: Optional[str] = None,
    ) -> None:
        self.network = network
        self.portal_url = portal_url
        self.should_run = True

        self.event_bus = EventBus()
        self.retry_engine = RetryEngine(
            RetryConfig(
                initial_delay=5.0,
                max_delay=300.0,
                multiplier=2.0,
                jitter=0.25,
                max_attempts=10,
                circuit_reset_time=600.0,
            )
        )

        self.state_machine = ConnectionStateMachine(
            on_transition=self._on_state_transition,
        )
        self.monitor = NetworkMonitor()

        self.stats_db = StatsDatabase()
        self.session_tracker = SessionTracker()

        self.last_event_time: float = time.time()
        self.reconciliation_interval = 30.0  # seconds

        self.fault_tracker = FaultTracker()

        # Adaptive CAPTCHA cooldown
        self.browser_open_count = 0
        self.last_browser_open_time = 0.0

        # Startup reconciliation state
        self._startup_time: float = time.time()
        self._last_startup_probe: float = 0.0

        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum: int, frame) -> None:
        logger.info(
            "Signal received, initiating shutdown",
            extra={"action": "SHUTDOWN", "signal": signum},
        )
        self.should_run = False
        self.monitor.stop()

    def _on_state_transition(
        self,
        old_state: ConnectionState,
        new_state: ConnectionState,
    ) -> None:
        """Map internal state transitions to event bus and retry engine."""
        if not self.network:
            from captivity.daemon.network_monitor import get_active_wifi_ssid

            self.network = get_active_wifi_ssid()

        network_name = self.network or "unknown"
        if new_state == ConnectionState.CONNECTED:
            self.retry_engine.record_success()
            self.browser_open_count = 0  # Reset CAPTCHA cooldown
            if not (
                self.session_tracker.current and self.session_tracker.current.is_active
            ):
                self.event_bus.publish(Event.LOGIN_SUCCESS)
                self.stats_db.record_login_success(network_name)
                self.session_tracker.start(network_name)
        elif new_state == ConnectionState.ERROR:
            self.retry_engine.record_failure(FailureType.TRANSIENT)
            if old_state in (ConnectionState.AUTHENTICATING, ConnectionState.PORTAL):
                self.stats_db.record_login_failure(network_name, "transition_error")

        if new_state in (
            ConnectionState.ERROR,
            ConnectionState.PORTAL,
            ConnectionState.INIT,
        ):
            ended_session = self.session_tracker.end()
            if ended_session:
                self.event_bus.publish(Event.SESSION_EXPIRED)
                self.stats_db.record_session_end(
                    network=ended_session.network,
                    duration=ended_session.duration,
                )

        if old_state == ConnectionState.ERROR and new_state == ConnectionState.PROBING:
            self.stats_db.record_reconnect(network_name)

    def _should_open_browser(self) -> bool:
        """Adaptive cooldown logic for CAPTCHA browser opening."""
        cooldowns = [0, 60, 120]  # 1st: immediate, 2nd: 60s, 3rd: 120s
        idx = min(self.browser_open_count, len(cooldowns) - 1)
        cooldown = cooldowns[idx]

        # Max cooldown cap
        if self.browser_open_count >= len(cooldowns):
            cooldown = 300

        elapsed = time.time() - self.last_browser_open_time
        if elapsed >= cooldown:
            self.browser_open_count += 1
            self.last_browser_open_time = time.time()
            logger.info(
                "Browser cooldown passed, allowing open",
                extra={
                    "action": "ALLOW_OPEN",
                    "count": self.browser_open_count,
                    "cooldown_seconds": cooldown,
                },
            )
            return True

        logger.debug(
            "Browser cooldown active", extra={"remaining_seconds": cooldown - elapsed}
        )
        return False

    def _in_startup_window(self) -> bool:
        """Return True if we are still inside the startup reconciliation window."""
        return (time.time() - self._startup_time) < STARTUP_RECONCILIATION_WINDOW

    def _startup_reconciliation_due(self) -> bool:
        """Return True if it is time for the next startup-window probe."""
        if not self._in_startup_window():
            return False
        return (
            time.time() - self._last_startup_probe
        ) >= STARTUP_RECONCILIATION_INTERVAL

    def _run_probe(self) -> None:
        """Execute connectivity probe and force state transition (Global Truth Rule)."""
        now = time.time()
        elapsed = now - self._startup_time

        if self._in_startup_window():
            logger.info(
                "STARTUP_RECONCILIATION",
                extra={
                    "active": True,
                    "elapsed_s": round(elapsed, 1),
                    "forcing_probe": True,
                },
            )

        self._last_startup_probe = now
        self.state_machine.force_transition(ConnectionState.PROBING)

        result = probe_connectivity_detailed(url=self.portal_url or "")

        logger.info(
            "PROBE RESULT: %s | CONFIDENCE: %.2f | PORTAL: %s | CAPTCHA: %s | METHOD: %s",
            result.status.value,
            getattr(result, "confidence", 1.0),
            getattr(result, "has_captive_portal", False),
            getattr(result, "has_captcha", False),
            result.detection_method,
        )
        logger.info("Probe complete")

        if result.status == ConnectivityStatus.CONNECTED:
            self.state_machine.force_transition(ConnectionState.CONNECTED)
        elif result.status == ConnectivityStatus.NETWORK_UNAVAILABLE:
            self.state_machine.force_transition(ConnectionState.ERROR)
        elif result.status == ConnectivityStatus.PORTAL_DETECTED:
            self.state_machine.force_transition(ConnectionState.PORTAL)
            self._handle_portal()

    def _handle_portal(self) -> None:
        """Attempt to login to the portal."""
        if not self.network:
            from captivity.daemon.network_monitor import get_active_wifi_ssid

            self.network = get_active_wifi_ssid()

        if not self.network:
            logger.error(
                "Login failed", extra={"reason": "No active WiFi network known"}
            )
            self.state_machine.transition(ConnectionState.ERROR)
            return

        try:
            self.state_machine.transition(ConnectionState.AUTHENTICATING)
        except InvalidTransition:
            pass

        try:
            open_browser = self._should_open_browser()
            login_result = do_login(
                network=self.network,
                portal_url=self.portal_url,
                open_browser=open_browser,
            )

            if login_result == LoginResult.SUCCESS:
                logger.info("Login complete", extra={"result": "SUCCESS"})
                self.state_machine.transition(ConnectionState.CONNECTED)
            elif login_result == LoginResult.WAIT_USER:
                logger.info(
                    "Login deferred to user",
                    extra={"result": "WAIT_USER", "action": "POLL_BACKGROUND"},
                )
                self.state_machine.transition(ConnectionState.WAIT_USER)
            else:
                logger.warning("Login failed", extra={"result": "FAILED"})
                self.state_machine.transition(ConnectionState.ERROR)

        except Exception as exc:
            logger.error(
                "Login encountered an error: %s",
                exc,
                exc_info=True,
            )
            self.state_machine.transition(ConnectionState.ERROR)

    def _handle_network_event(self, event: NetworkEvent) -> None:
        """Handle normalized events from the network monitor."""
        self.last_event_time = time.time()
        logger.info("Network event received", extra={"event": event.name})

        if event == NetworkEvent.DISCONNECTED:
            self.state_machine.transition(ConnectionState.ERROR)
        elif event in (NetworkEvent.CONNECTED, NetworkEvent.PORTAL):
            # Regardless of what NM says, trust but verify
            self._run_probe()

    def run(self) -> None:
        """Failure-proof main event loop."""
        logger.info(
            "Daemon starting up",
            extra={
                "action": "INIT",
                "startup_reconciliation_window_s": STARTUP_RECONCILIATION_WINDOW,
                "startup_reconciliation_interval_s": STARTUP_RECONCILIATION_INTERVAL,
            },
        )
        self.monitor.start()

        # Brief stabilisation: let NetworkManager settle NIC association, ARP, DHCP.
        # We do NOT rely on this being sufficient — the reconciliation window covers any gap.
        time.sleep(2.0)
        self._run_probe()

        while self.should_run:
            try:
                # 1. Block on queue with 1s heartbeat
                event = self.monitor.get_event(timeout=1.0)

                if event:
                    self._handle_network_event(event)

                # 2. Watchdog Invariant Enforcement
                self.state_machine.check_watchdog()

                # 3a. Startup Reconciliation Window
                # Probe every STARTUP_RECONCILIATION_INTERVAL seconds regardless of
                # event delivery.  Covers WiFi-late-association and missed NM events.
                if self._startup_reconciliation_due():
                    elapsed = time.time() - self._startup_time
                    logger.info(
                        "STARTUP_RECONCILIATION",
                        extra={
                            "active": True,
                            "elapsed_s": round(elapsed, 1),
                            "forcing_probe": True,
                        },
                    )
                    self._run_probe()
                    self.last_event_time = time.time()
                    continue

                # 3b. Steady-state Reconciliation Loop (Event Loss Handling)
                if time.time() - self.last_event_time > self.reconciliation_interval:
                    self.last_event_time = time.time()

                    if self.state_machine.state in (
                        ConnectionState.WAIT_USER,
                        ConnectionState.CONNECTED,
                    ):
                        result = probe_connectivity_detailed()
                        if self.state_machine.state == ConnectionState.WAIT_USER:
                            if result.status == ConnectivityStatus.CONNECTED:
                                logger.info(
                                    "Reconciliation loop restored internet connection",
                                    extra={
                                        "result": "INTERNET_RESTORED",
                                        "action": "CONNECTED",
                                    },
                                )
                                self.state_machine.transition(ConnectionState.CONNECTED)
                            elif result.status == ConnectivityStatus.PORTAL_DETECTED:
                                pass  # Watchdog will push to RETRY
                        elif self.state_machine.state == ConnectionState.CONNECTED:
                            if result.status != ConnectivityStatus.CONNECTED:
                                logger.warning(
                                    "Reconciliation loop lost connection",
                                    extra={
                                        "result": "CONNECTION_LOST",
                                        "action": "PROBE",
                                    },
                                )
                                self._run_probe()

                    elif self.state_machine.state in (
                        ConnectionState.INIT,
                        ConnectionState.ERROR,
                        ConnectionState.RETRY,
                    ):
                        # Time-based probe reconciliation: even outside the startup window,
                        # if we have been stuck in a non-terminal state with no events,
                        # force a fresh probe so we never idle forever.
                        logger.info(
                            "Time-based reconciliation probe",
                            extra={
                                "state": self.state_machine.state.name,
                                "action": "PROBE",
                            },
                        )
                        self._run_probe()

                # 4. Retry Engine Handling
                if self.state_machine.state == ConnectionState.RETRY:
                    if self.retry_engine.should_retry():
                        logger.info(
                            "Triggering retry probe",
                            extra={
                                "action": "PROBE",
                                "attempt": self.retry_engine.attempt,
                            },
                        )
                        self._run_probe()

            except Exception as exc:
                # Phase 6: Crash Resilience
                sleep_delay = self.fault_tracker.record_crash()
                logger.error(
                    "Crash loop prevention activated",
                    extra={
                        "exception": str(exc),
                        "action": "SLEEP",
                        "sleep_seconds": sleep_delay,
                    },
                    exc_info=True,
                )
                if self.should_run:
                    time.sleep(sleep_delay)
                # Ensure we recover to a safe state
                try:
                    self.state_machine.transition(ConnectionState.ERROR)
                except InvalidTransition:
                    pass

        logger.info("Daemon shutting down", extra={"action": "STOP"})
