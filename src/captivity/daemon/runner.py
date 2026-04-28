"""
Daemon reconnect loop for Captivity.

Integrates all core components:
  - Connection state machine for explicit state tracking
  - Smart retry engine with exponential backoff + jitter
  - Event bus for decoupled publish/subscribe
  - DBus monitor for NM connectivity state (falls back to polling)
  - Plugin-based login via the login engine
  - Telemetry stats for connection event recording

Monitors connectivity and automatically logs into captive
portals when detected. Supports exponential backoff retry
with circuit breaker and graceful shutdown via signals.
"""

import signal
import time
from typing import Optional

from captivity.core.probe import probe_connectivity, ConnectivityStatus
from captivity.core.login import do_login, LoginError
from captivity.core.credentials import CredentialError
from captivity.core.state import (
    ConnectionState,
    ConnectionStateMachine,
    InvalidTransition,
)
from captivity.core.retry import RetryEngine, RetryConfig, FailureType, RetryState
from captivity.daemon.events import Event, EventBus
from captivity.daemon.dbus_monitor import DBusMonitor, NMConnectivityState
from captivity.utils.logging import get_logger

logger = get_logger("daemon")

DEFAULT_INTERVAL = 30


class DaemonRunner:
    """Reconnect daemon with event-driven architecture.

    Integrates state machine, event bus, retry engine, and DBus
    monitoring for efficient captive portal detection and login.

    Attributes:
        network: Network name for credential lookup.
        portal_url: Optional portal URL override.
        interval: Probe interval in seconds.
        should_run: Flag to control the main loop.
        state_machine: Connection state tracker.
        event_bus: Internal event dispatcher.
        dbus_monitor: NetworkManager state monitor.
        retry_engine: Smart retry with backoff, jitter, circuit breaker.
    """

    def __init__(
        self,
        network: Optional[str] = None,
        portal_url: Optional[str] = None,
        interval: int = DEFAULT_INTERVAL,
    ) -> None:
        self.network = network
        self.portal_url = portal_url
        self.interval = interval
        self.should_run = True

        # Core components
        self.event_bus = EventBus()
        self.retry_engine = RetryEngine(RetryConfig(
            initial_delay=5.0,
            max_delay=300.0,
            multiplier=2.0,
            jitter=0.25,
            max_attempts=10,
            circuit_reset_time=600.0,
        ))
        self.state_machine = ConnectionStateMachine(
            on_transition=self._on_state_transition,
            retry_engine=self.retry_engine,
            event_bus=self.event_bus,
        )
        self.dbus_monitor = DBusMonitor()

        # Telemetry (lazy-loaded to avoid import issues in tests)
        self._stats_db = None

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _get_stats_db(self):
        """Lazy-load stats database for telemetry recording."""
        if self._stats_db is None:
            try:
                from captivity.telemetry.stats import StatsDatabase
                self._stats_db = StatsDatabase()
            except Exception as exc:
                logger.debug("Stats database unavailable: %s", exc)
        return self._stats_db

    def _handle_signal(self, signum: int, frame) -> None:
        """Handle shutdown signals gracefully."""
        sig_name = signal.Signals(signum).name
        logger.info("Received %s — shutting down gracefully", sig_name)
        self.should_run = False

    def _on_state_transition(
        self,
        old_state: ConnectionState,
        new_state: ConnectionState,
    ) -> None:
        """Callback for state machine transitions.

        Maps state transitions to event bus events and records telemetry.
        """
        event_map = {
            ConnectionState.NETWORK_CONNECTED: Event.NETWORK_CONNECTED,
            ConnectionState.PORTAL_DETECTED: Event.PORTAL_DETECTED,
            ConnectionState.CONNECTED: Event.LOGIN_SUCCESS,
            ConnectionState.NETWORK_UNAVAILABLE: Event.SESSION_EXPIRED,
        }

        event = event_map.get(new_state)
        if event:
            self.event_bus.publish(
                event,
                old_state=old_state.name,
                new_state=new_state.name,
            )

    def _get_retry_delay(self) -> float:
        """Get delay from retry engine (replaces primitive backoff list)."""
        delay = self.retry_engine.get_delay()
        if delay < 0:
            # Circuit open — use a long delay before re-checking
            return self.retry_engine.config.circuit_reset_time
        return max(delay, self.interval)

    def _sleep(self, duration: float) -> None:
        """Interruptible sleep."""
        elapsed = 0.0
        while elapsed < duration and self.should_run:
            time.sleep(1)
            elapsed += 1.0

    def _detect_network(self) -> None:
        """Auto-detect WiFi SSID if no network specified."""
        if self.network:
            return

        ssid = self.dbus_monitor.wifi_ssid
        if ssid:
            self.network = ssid
            logger.info("Auto-detected WiFi SSID: %s", ssid)

    def _record_event(self, event_type: str, details: str = "") -> None:
        """Record a telemetry event if stats database is available."""
        db = self._get_stats_db()
        if db and self.network:
            try:
                if event_type == "login_success":
                    db.record_login_success(self.network)
                elif event_type == "login_failure":
                    db.record_login_failure(self.network, details)
                elif event_type == "reconnect":
                    db.record_reconnect(self.network)
            except Exception as exc:
                logger.debug("Failed to record event: %s", exc)

    def _attempt_login(self) -> bool:
        """Attempt to login to the captive portal.

        Uses retry engine for intelligent failure handling:
        - Classifies errors (transient/auth/rate-limited/portal-down)
        - Applies exponential backoff with jitter
        - Opens circuit breaker after repeated failures

        Returns:
            True if login succeeded, False otherwise.
        """
        self._detect_network()

        if not self.network:
            logger.error("Cannot login: no network name (use --network or connect to WiFi)")
            return False

        # Check if retry engine allows attempt
        if not self.retry_engine.should_retry():
            state = self.retry_engine.state
            if state == RetryState.CIRCUIT_OPEN:
                logger.warning(
                    "Circuit breaker OPEN — skipping login (resets in %.0fs)",
                    self.retry_engine.config.circuit_reset_time,
                )
            return False

        try:
            self.state_machine.transition(ConnectionState.LOGGING_IN)
        except InvalidTransition:
            pass

        try:
            kwargs = {"network": self.network}
            if self.portal_url:
                kwargs["portal_url"] = self.portal_url

            success = do_login(**kwargs)

            if success:
                self.retry_engine.record_success()
                self._record_event("login_success")
                try:
                    self.state_machine.transition(ConnectionState.CONNECTED)
                except InvalidTransition:
                    pass
                return True
            else:
                failure_type = FailureType.TRANSIENT
                self.retry_engine.record_failure(failure_type)
                self._record_event("login_failure", "login returned false")
                try:
                    self.state_machine.transition(ConnectionState.PORTAL_DETECTED)
                except InvalidTransition:
                    pass
                self.event_bus.publish(Event.LOGIN_FAILURE)
                return False

        except CredentialError as exc:
            # Auth errors — circuit breaker should open immediately
            self.retry_engine.record_failure(FailureType.AUTH_ERROR)
            self._record_event("login_failure", f"credential error: {exc}")
            logger.error("Login failed (credentials): %s", exc)
            try:
                self.state_machine.transition(ConnectionState.PORTAL_DETECTED)
            except InvalidTransition:
                pass
            self.event_bus.publish(Event.LOGIN_FAILURE, error=str(exc))
            return False

        except LoginError as exc:
            # Classify the error for intelligent retry
            failure_type = RetryEngine.classify_error(str(exc))
            self.retry_engine.record_failure(failure_type)
            self._record_event("login_failure", f"{failure_type.value}: {exc}")
            logger.error("Login failed (%s): %s", failure_type.value, exc)
            try:
                self.state_machine.transition(ConnectionState.PORTAL_DETECTED)
            except InvalidTransition:
                pass
            self.event_bus.publish(Event.LOGIN_FAILURE, error=str(exc))
            return False

    def run_once(self) -> ConnectivityStatus:
        """Run a single connectivity probe and handle the result.

        Uses DBus monitor if available for quicker detection.

        Returns:
            The connectivity status detected.
        """
        # Check DBus first for instant detection
        nm_change = self.dbus_monitor.check_connectivity_changed()
        if nm_change == NMConnectivityState.PORTAL:
            logger.info("NM reports: captive portal")
            try:
                self.state_machine.transition(ConnectionState.PORTAL_DETECTED)
            except InvalidTransition:
                pass
            self._attempt_login()
            return ConnectivityStatus.PORTAL_DETECTED

        if nm_change == NMConnectivityState.FULL:
            logger.debug("NM reports: full connectivity")
            try:
                self.state_machine.transition(ConnectionState.CONNECTED)
            except InvalidTransition:
                pass
            self.retry_engine.record_success()
            return ConnectivityStatus.CONNECTED

        # Fallback to HTTP probe
        status, redirect_url = probe_connectivity()

        if status == ConnectivityStatus.CONNECTED:
            logger.debug("Status: CONNECTED")
            self.retry_engine.record_success()
            try:
                self.state_machine.transition(ConnectionState.CONNECTED)
            except InvalidTransition:
                pass

        elif status == ConnectivityStatus.PORTAL_DETECTED:
            logger.info("Status: CAPTIVE PORTAL DETECTED")
            if redirect_url:
                logger.info("Portal redirect: %s", redirect_url)
            try:
                self.state_machine.transition(ConnectionState.PORTAL_DETECTED)
            except InvalidTransition:
                pass
            self._attempt_login()

        elif status == ConnectivityStatus.NETWORK_UNAVAILABLE:
            self.retry_engine.record_failure(FailureType.TRANSIENT)
            self._record_event("network_unavailable")
            delay = self.retry_engine.get_delay()
            logger.warning(
                "Status: NETWORK UNAVAILABLE (attempt %d, retry in %.1fs)",
                self.retry_engine.attempt,
                delay,
            )
            try:
                self.state_machine.transition(ConnectionState.NETWORK_UNAVAILABLE)
            except InvalidTransition:
                pass

        return status

    def run(self) -> None:
        """Run the reconnect loop continuously.

        Probes connectivity at regular intervals and triggers
        login when a captive portal is detected. Uses smart
        retry engine with exponential backoff, jitter, and
        circuit breaker.
        """
        logger.info(
            "Starting captivity daemon v2.1 (interval: %ds, retry: exponential backoff)",
            self.interval,
        )
        if self.network:
            logger.info("Network: %s", self.network)
        if self.portal_url:
            logger.info("Portal:  %s", self.portal_url)
        logger.info(
            "DBus: %s",
            "enabled" if self.dbus_monitor.available else "unavailable (polling)",
        )
        logger.info(
            "Retry: max_attempts=%d, max_delay=%.0fs, circuit_reset=%.0fs",
            self.retry_engine.config.max_attempts,
            self.retry_engine.config.max_delay,
            self.retry_engine.config.circuit_reset_time,
        )

        self.event_bus.publish(Event.DAEMON_START)
        self._record_event("daemon_start")

        while self.should_run:
            status = self.run_once()

            if status == ConnectivityStatus.NETWORK_UNAVAILABLE:
                delay = self.retry_engine.get_delay()
                if delay < 0:
                    logger.warning("Circuit breaker OPEN — waiting for reset")
                    delay = self.retry_engine.config.circuit_reset_time
                self._sleep(delay)
            elif status == ConnectivityStatus.PORTAL_DETECTED:
                # After failed login, use retry delay
                delay = self.retry_engine.get_delay()
                if delay > 0:
                    self._sleep(delay)
                else:
                    self._sleep(self.interval)
            else:
                self._sleep(self.interval)

        self.event_bus.publish(Event.DAEMON_STOP)
        self._record_event("daemon_stop")
        logger.info("Daemon stopped")
