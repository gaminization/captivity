"""
Internal event bus for Captivity.

Provides a lightweight publish/subscribe mechanism for decoupled
communication between daemon components.

Events:
    NETWORK_CONNECTED     — WiFi interface connected
    PORTAL_DETECTED       — Captive portal detected via probe
    LOGIN_SUCCESS         — Login completed successfully
    LOGIN_FAILURE         — Login attempt failed
    SESSION_EXPIRED       — Internet access lost (was connected)
    SYSTEM_RESUME         — System resumed from suspend
    DAEMON_START          — Daemon started
    DAEMON_STOP           — Daemon stopping
"""

import threading
from enum import Enum, auto
from typing import Callable, Any

from captivity.utils.logging import get_logger

logger = get_logger("events")


class Event(Enum):
    """Event types published on the event bus."""

    NETWORK_CONNECTED = auto()
    PORTAL_DETECTED = auto()
    LOGIN_SUCCESS = auto()
    LOGIN_FAILURE = auto()
    SESSION_EXPIRED = auto()
    SYSTEM_RESUME = auto()
    DAEMON_START = auto()
    DAEMON_STOP = auto()


class EventBus:
    """Thread-safe publish/subscribe event dispatcher.

    Subscribers register callbacks for specific event types.
    When an event is published, all registered callbacks are
    invoked synchronously in registration order.

    Usage:
        bus = EventBus()
        bus.subscribe(Event.PORTAL_DETECTED, handle_portal)
        bus.publish(Event.PORTAL_DETECTED, redirect_url="http://...")
    """

    def __init__(self) -> None:
        self._subscribers: dict[Event, list[Callable]] = {}
        self._lock = threading.Lock()

    def subscribe(
        self,
        event: Event,
        callback: Callable[..., None],
    ) -> None:
        """Register a callback for an event type.

        Args:
            event: Event type to subscribe to.
            callback: Function to call when event is published.
        """
        with self._lock:
            if event not in self._subscribers:
                self._subscribers[event] = []
            self._subscribers[event].append(callback)
            logger.debug(
                "Subscribed %s to %s",
                callback.__name__,
                event.name,
            )

    def unsubscribe(
        self,
        event: Event,
        callback: Callable[..., None],
    ) -> None:
        """Remove a callback subscription.

        Args:
            event: Event type to unsubscribe from.
            callback: Callback function to remove.
        """
        with self._lock:
            if event in self._subscribers:
                try:
                    self._subscribers[event].remove(callback)
                except ValueError:
                    pass

    def publish(self, event: Event, **kwargs: Any) -> None:
        """Publish an event to all subscribers.

        Args:
            event: Event type to publish.
            **kwargs: Event data passed to callbacks.
        """
        with self._lock:
            subscribers = list(self._subscribers.get(event, []))

        if not subscribers:
            logger.debug("No subscribers for %s", event.name)
            return

        logger.debug(
            "Publishing %s to %d subscribers",
            event.name,
            len(subscribers),
        )

        for callback in subscribers:
            try:
                callback(event=event, **kwargs)
            except Exception as exc:
                logger.error(
                    "Subscriber %s raised: %s",
                    callback.__name__,
                    exc,
                )

    def clear(self) -> None:
        """Remove all subscriptions."""
        with self._lock:
            self._subscribers.clear()

    @property
    def subscriber_count(self) -> int:
        """Total number of subscriptions across all events."""
        with self._lock:
            return sum(len(subs) for subs in self._subscribers.values())
