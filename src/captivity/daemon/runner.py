"""
Daemon reconnect loop for Captivity.

Continuously monitors connectivity and automatically logs into
captive portals when detected. Supports exponential backoff
retry and graceful shutdown via signals.
"""

import signal
import time
from typing import Optional

from captivity.core.probe import probe_connectivity, ConnectivityStatus
from captivity.core.login import do_login, LoginError
from captivity.core.credentials import CredentialError
from captivity.utils.logging import get_logger

logger = get_logger("daemon")

# Backoff intervals in seconds
BACKOFF_INTERVALS = [5, 10, 30, 60, 120, 300]
DEFAULT_INTERVAL = 30


class DaemonRunner:
    """Reconnect daemon that monitors connectivity and auto-logins.

    Attributes:
        network: Network name for credential lookup.
        portal_url: Optional portal URL override.
        interval: Probe interval in seconds.
        should_run: Flag to control the main loop.
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

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum: int, frame) -> None:
        """Handle shutdown signals gracefully."""
        sig_name = signal.Signals(signum).name
        logger.info("Received %s — shutting down gracefully", sig_name)
        self.should_run = False

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

    def _attempt_login(self) -> bool:
        """Attempt to login to the captive portal.

        Returns:
            True if login succeeded, False otherwise.
        """
        if not self.network:
            logger.error("Cannot login: no --network specified")
            return False

        try:
            kwargs = {"network": self.network}
            if self.portal_url:
                kwargs["portal_url"] = self.portal_url

            success = do_login(**kwargs)

            if success:
                self._consecutive_failures = 0
                return True
            else:
                self._consecutive_failures += 1
                return False

        except (LoginError, CredentialError) as exc:
            self._consecutive_failures += 1
            logger.error("Login failed: %s", exc)
            return False

    def run_once(self) -> ConnectivityStatus:
        """Run a single connectivity probe and handle the result.

        Returns:
            The connectivity status detected.
        """
        status, redirect_url = probe_connectivity()

        if status == ConnectivityStatus.CONNECTED:
            logger.debug("Status: CONNECTED")
            self._consecutive_failures = 0

        elif status == ConnectivityStatus.PORTAL_DETECTED:
            logger.info("Status: CAPTIVE PORTAL DETECTED")
            if redirect_url:
                logger.info("Portal redirect: %s", redirect_url)
            self._attempt_login()

        elif status == ConnectivityStatus.NETWORK_UNAVAILABLE:
            self._consecutive_failures += 1
            backoff = self._get_backoff()
            logger.warning(
                "Status: NETWORK UNAVAILABLE (failure %d, backoff %ds)",
                self._consecutive_failures,
                backoff,
            )

        return status

    def run(self) -> None:
        """Run the reconnect loop continuously.

        Probes connectivity at regular intervals and triggers
        login when a captive portal is detected. Uses exponential
        backoff on failures.
        """
        logger.info("Starting captivity daemon (interval: %ds)", self.interval)
        if self.network:
            logger.info("Network: %s", self.network)
        if self.portal_url:
            logger.info("Portal:  %s", self.portal_url)

        while self.should_run:
            status = self.run_once()

            if status == ConnectivityStatus.NETWORK_UNAVAILABLE:
                backoff = self._get_backoff()
                self._sleep(backoff)
            else:
                self._sleep(self.interval)

        logger.info("Daemon stopped")
