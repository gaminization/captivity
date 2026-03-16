"""
GTK3 system tray icon for Captivity.

Provides a status icon in the system tray showing connection
state. Integrates with the event bus to update icon and send
notifications on state changes.

Requires: PyGObject (gi) with Gtk 3.0
Falls back gracefully if GTK is unavailable.
"""

from typing import Optional

from captivity.daemon.events import Event, EventBus
from captivity.ui.notifier import Notifier
from captivity.utils.logging import get_logger

logger = get_logger("tray")

# Icon names mapping connection states
ICONS = {
    "connected": "network-wireless-signal-excellent",
    "portal": "network-wireless-acquiring",
    "offline": "network-wireless-offline",
    "idle": "network-wireless-signal-ok",
    "error": "network-wireless-error",
}


def is_gtk_available() -> bool:
    """Check if GTK3 is available for import."""
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # noqa: F401
        return True
    except (ImportError, ValueError):
        return False


class TrayIcon:
    """GTK3 system tray status icon.

    Shows connection status via icon changes and provides
    a right-click context menu with basic controls.

    Integrates with EventBus for automatic status updates
    and Notifier for desktop notifications.

    Attributes:
        event_bus: Event dispatcher for status updates.
        notifier: Desktop notification sender.
        network: Current network name.
        status: Current connection status string.
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        notifier: Optional[Notifier] = None,
        network: str = "",
    ) -> None:
        self.event_bus = event_bus or EventBus()
        self.notifier = notifier or Notifier()
        self.network = network
        self.status = "idle"
        self._icon = None
        self._menu = None
        self._gtk_available = is_gtk_available()

        if not self._gtk_available:
            logger.warning("GTK3 not available — tray icon disabled")
        else:
            self._setup_icon()

        # Always subscribe to events (notifications work without GTK)
        self._subscribe_events()

    def _setup_icon(self) -> None:
        """Create the GTK StatusIcon and context menu."""
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        # Create status icon
        self._icon = Gtk.StatusIcon()
        self._icon.set_from_icon_name(ICONS["idle"])
        self._icon.set_tooltip_text("Captivity — Idle")
        self._icon.set_visible(True)

        # Connect popup menu signal
        self._icon.connect("popup-menu", self._on_popup_menu)

        # Build context menu
        self._menu = Gtk.Menu()

        status_item = Gtk.MenuItem(label="Status: Idle")
        status_item.set_sensitive(False)
        self._menu.append(status_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        probe_item = Gtk.MenuItem(label="Probe Now")
        probe_item.connect("activate", self._on_probe)
        self._menu.append(probe_item)

        login_item = Gtk.MenuItem(label="Login Now")
        login_item.connect("activate", self._on_login)
        self._menu.append(login_item)

        self._menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit)
        self._menu.append(quit_item)

        self._menu.show_all()

        logger.info("System tray icon created")

    def _subscribe_events(self) -> None:
        """Subscribe to event bus for automatic status updates."""
        self.event_bus.subscribe(Event.LOGIN_SUCCESS, self._on_login_success)
        self.event_bus.subscribe(Event.LOGIN_FAILURE, self._on_login_failure)
        self.event_bus.subscribe(Event.PORTAL_DETECTED, self._on_portal_detected)
        self.event_bus.subscribe(Event.SESSION_EXPIRED, self._on_session_expired)
        self.event_bus.subscribe(Event.NETWORK_CONNECTED, self._on_network_connected)

    def _update_icon(self, status: str, tooltip: str) -> None:
        """Update tray icon and tooltip."""
        self.status = status
        if self._icon:
            icon_name = ICONS.get(status, ICONS["idle"])
            self._icon.set_from_icon_name(icon_name)
            self._icon.set_tooltip_text(f"Captivity — {tooltip}")

        if self._menu:
            items = self._menu.get_children()
            if items:
                items[0].set_label(f"Status: {tooltip}")

    # Event handlers
    def _on_login_success(self, **kwargs) -> None:
        self._update_icon("connected", f"Connected ({self.network})")
        self.notifier.notify_login_success(self.network)

    def _on_login_failure(self, **kwargs) -> None:
        error = kwargs.get("error", "")
        self._update_icon("error", "Login Failed")
        self.notifier.notify_login_failure(self.network, error)

    def _on_portal_detected(self, **kwargs) -> None:
        self._update_icon("portal", "Portal Detected")
        self.notifier.notify_portal_detected(self.network)

    def _on_session_expired(self, **kwargs) -> None:
        self._update_icon("offline", "Session Expired")
        self.notifier.notify_session_expired(self.network)

    def _on_network_connected(self, **kwargs) -> None:
        self._update_icon("idle", "Network Connected")

    # Menu handlers
    def _on_popup_menu(self, icon, button, time) -> None:
        if self._menu:
            self._menu.popup(None, None, None, None, button, time)

    def _on_probe(self, widget) -> None:
        """Trigger a manual connectivity probe."""
        self.event_bus.publish(Event.PORTAL_DETECTED, manual=True)
        logger.info("Manual probe triggered from tray")

    def _on_login(self, widget) -> None:
        """Trigger a manual login attempt."""
        logger.info("Manual login triggered from tray")

    def _on_quit(self, widget) -> None:
        """Quit the tray application."""
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
        logger.info("Tray application quit")
        Gtk.main_quit()

    def run(self) -> None:
        """Start the GTK main loop.

        This blocks until Gtk.main_quit() is called.
        """
        if not self._gtk_available:
            logger.error("Cannot start tray: GTK3 not available")
            return

        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        logger.info("Starting tray application")
        self.notifier.notify_daemon_started()

        try:
            Gtk.main()
        except KeyboardInterrupt:
            logger.info("Tray interrupted")
