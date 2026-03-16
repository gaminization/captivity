"""
Daemon reconnect loop for Captivity.

Integrates all v0.6–v0.9 components:
  - Connection state machine for explicit state tracking
  - Event bus for decoupled publish/subscribe
  - DBus monitor for NM connectivity state (falls back to polling)
  - Plugin-based login via the login engine

Monitors connectivity and automatically logs into captive
portals when detected. Supports exponential backoff retry
and graceful shutdown via signals.
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
from captivity.daemon.events import Event, EventBus
from captivity.daemon.dbus_monitor import DBusMonitor, NMConnectivityState
from captivity.utils.logging import get_logger

logger = get_logger("daemon")

# Backoff intervals in seconds
BACKOFF_INTERVALS = [5, 10, 30, 60, 120, 300]
DEFAULT_INTERVAL = 30


class DaemonRunner:
    """Reconnect daemon with event-driven architecture.

    Integrates state machine, event bus, and DBus monitoring
    for efficient captive portal detection and login.

    Attributes:
        network: Network name for credential lookup.
        portal_url: Optional portal URL override.
        interval: Probe interval in seconds.
        should_run: Flag to control the main loop.
        state_machine: Connection state tracker.
        event_bus: Internal event dispatcher.
        dbus_monitor: NetworkManager state monitor.
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
        self._consecutive_failures = 0

        # Core components
        self.event_bus = EventBus()
        self.state_machine = ConnectionStateMachine(
            on_transition=self._on_state_transition,
        )
        self.dbus_monitor = DBusMonitor()

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

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

        Maps state transitions to event bus events.
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

    def _get_backoff(self) -> int:
        """Calculate backoff interval based on consecutive failures."""
        idx = min(self._consecutive_failures, len(BACKOFF_INTERVALS) - 1)
        return BACKOFF_INTERVALS[idx]

    def _sleep(self, duration: int) -> None:
        """Interruptible sleep."""
        elapsed = 0
        while elapsed < duration and self.should_run:
            time.sleep(1)
            elapsed += 1

    def _detect_network(self) -> None:
        """Auto-detect WiFi SSID if no network specified."""
        if self.network:
            return

        ssid = self.dbus_monitor.wifi_ssid
        if ssid:
            self.network = ssid
            logger.info("Auto-detected WiFi SSID: %s", ssid)

    def _attempt_login(self) -> bool:
        """Attempt to login to the captive portal.

        Returns:
            True if login succeeded, False otherwise.
        """
        self._detect_network()

        if not self.network:
            logger.error("Cannot login: no network name (use --network or connect to WiFi)")
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
                self._consecutive_failures = 0
                try:
                    self.state_machine.transition(ConnectionState.CONNECTED)
                except InvalidTransition:
                    pass
                return True
            else:
                self._consecutive_failures += 1
                try:
                    self.state_machine.transition(ConnectionState.PORTAL_DETECTED)
                except InvalidTransition:
                    pass
                self.event_bus.publish(Event.LOGIN_FAILURE)
                return False

        except (LoginError, CredentialError) as exc:
            self._consecutive_failures += 1
            logger.error("Login failed: %s", exc)
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
            self._consecutive_failures = 0
            return ConnectivityStatus.CONNECTED

        # Fallback to HTTP probe
        status, redirect_url = probe_connectivity()

        if status == ConnectivityStatus.CONNECTED:
            logger.debug("Status: CONNECTED")
            self._consecutive_failures = 0
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
            self._consecutive_failures += 1
            backoff = self._get_backoff()
            logger.warning(
                "Status: NETWORK UNAVAILABLE (failure %d, backoff %ds)",
                self._consecutive_failures,
                backoff,
            )
            try:
                self.state_machine.transition(ConnectionState.NETWORK_UNAVAILABLE)
            except InvalidTransition:
                pass

        return status

    def run(self) -> None:
        """Run the reconnect loop continuously.

        Probes connectivity at regular intervals and triggers
        login when a captive portal is detected. Uses exponential
        backoff on failures.
        """
        logger.info("Starting captivity daemon v1.0 (interval: %ds)", self.interval)
        if self.network:
            logger.info("Network: %s", self.network)
        if self.portal_url:
            logger.info("Portal:  %s", self.portal_url)
        logger.info(
            "DBus: %s",
            "enabled" if self.dbus_monitor.available else "unavailable (polling)",
        )

        self.event_bus.publish(Event.DAEMON_START)

        while self.should_run:
            status = self.run_once()

            if status == ConnectivityStatus.NETWORK_UNAVAILABLE:
                backoff = self._get_backoff()
                self._sleep(backoff)
            else:
                self._sleep(self.interval)

        self.event_bus.publish(Event.DAEMON_STOP)
        logger.info("Daemon stopped")
