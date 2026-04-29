"""
Desktop notification system for Captivity.

Sends desktop notifications for login events using GLib's
Gio.Notification API via GDBus. Falls back to subprocess
`notify-send` if GLib is unavailable.

Notifications are non-blocking and will silently degrade
if no notification service is available.
"""

import shutil
import subprocess
from typing import Optional

from captivity.utils.logging import get_logger

logger = get_logger("notifier")

# Notification urgency levels
URGENCY_LOW = "low"
URGENCY_NORMAL = "normal"
URGENCY_CRITICAL = "critical"

# App identity
APP_NAME = "Captivity"
APP_ICON = "network-wireless"


def _has_notify_send() -> bool:
    """Check if notify-send is available."""
    return shutil.which("notify-send") is not None


def _send_via_notify_send(
    title: str,
    body: str,
    urgency: str = URGENCY_NORMAL,
    icon: str = APP_ICON,
) -> bool:
    """Send notification via notify-send subprocess.

    Args:
        title: Notification title.
        body: Notification body text.
        urgency: low, normal, or critical.
        icon: Icon name.

    Returns:
        True if notification was sent.
    """
    try:
        subprocess.run(
            [
                "notify-send",
                "--app-name",
                APP_NAME,
                "--urgency",
                urgency,
                "--icon",
                icon,
                title,
                body,
            ],
            capture_output=True,
            timeout=5,
        )
        return True
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("notify-send failed: %s", exc)
        return False


class Notifier:
    """Desktop notification manager.

    Sends notifications for captive portal events.
    Gracefully degrades if notification services are unavailable.

    Attributes:
        enabled: Whether notifications are enabled.
        available: Whether a notification backend is available.
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.available = _has_notify_send()

        if self.available:
            logger.info("Desktop notifications: enabled (notify-send)")
        else:
            logger.info("Desktop notifications: unavailable")

    def send(
        self,
        title: str,
        body: str,
        urgency: str = URGENCY_NORMAL,
        icon: Optional[str] = None,
    ) -> bool:
        """Send a desktop notification.

        Args:
            title: Notification title.
            body: Notification body text.
            urgency: Urgency level (low, normal, critical).
            icon: Optional icon name override.

        Returns:
            True if notification was sent successfully.
        """
        if not self.enabled or not self.available:
            logger.debug("Notification skipped: %s", title)
            return False

        return _send_via_notify_send(
            title=title,
            body=body,
            urgency=urgency,
            icon=icon or APP_ICON,
        )

    def notify_login_success(self, network: str) -> bool:
        """Notify user of successful login."""
        return self.send(
            title="WiFi Login Successful",
            body=f"Connected to {network}",
            urgency=URGENCY_LOW,
            icon="network-wireless-connected",
        )

    def notify_login_failure(self, network: str, error: str = "") -> bool:
        """Notify user of login failure."""
        body = f"Failed to login to {network}"
        if error:
            body += f": {error}"
        return self.send(
            title="WiFi Login Failed",
            body=body,
            urgency=URGENCY_NORMAL,
            icon="network-wireless-offline",
        )

    def notify_portal_detected(self, network: str) -> bool:
        """Notify user that a captive portal was detected."""
        return self.send(
            title="Captive Portal Detected",
            body=f"Portal found on {network}",
            urgency=URGENCY_LOW,
            icon="network-wireless-acquiring",
        )

    def notify_session_expired(self, network: str) -> bool:
        """Notify user that their session has expired."""
        return self.send(
            title="Session Expired",
            body=f"Connection lost on {network}. Reconnecting...",
            urgency=URGENCY_NORMAL,
            icon="network-wireless-offline",
        )

    def notify_daemon_started(self) -> bool:
        """Notify user that the daemon has started."""
        return self.send(
            title="Captivity Active",
            body="Monitoring WiFi connections",
            urgency=URGENCY_LOW,
        )
