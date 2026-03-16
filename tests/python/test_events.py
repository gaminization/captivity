"""Tests for captivity.daemon.events module."""

import unittest
from captivity.daemon.events import Event, EventBus


class TestEvent(unittest.TestCase):
    """Test Event enum."""

    def test_all_events_defined(self):
        events = list(Event)
        self.assertGreater(len(events), 5)
        self.assertIn(Event.NETWORK_CONNECTED, events)
        self.assertIn(Event.PORTAL_DETECTED, events)
        self.assertIn(Event.LOGIN_SUCCESS, events)
        self.assertIn(Event.SYSTEM_RESUME, events)


class TestEventBus(unittest.TestCase):
    """Test EventBus."""

    def setUp(self):
        self.bus = EventBus()
        self.received = []

    def _handler(self, **kwargs):
        self.received.append(kwargs)

    def test_subscribe_and_publish(self):
        self.bus.subscribe(Event.PORTAL_DETECTED, self._handler)
        self.bus.publish(Event.PORTAL_DETECTED, url="http://portal")

        self.assertEqual(len(self.received), 1)
        self.assertEqual(self.received[0]["url"], "http://portal")
        self.assertEqual(self.received[0]["event"], Event.PORTAL_DETECTED)

    def test_multiple_subscribers(self):
        results = []
        def handler1(**kwargs):
            results.append("h1")
        def handler2(**kwargs):
            results.append("h2")

        self.bus.subscribe(Event.LOGIN_SUCCESS, handler1)
        self.bus.subscribe(Event.LOGIN_SUCCESS, handler2)
        self.bus.publish(Event.LOGIN_SUCCESS)

        self.assertEqual(results, ["h1", "h2"])

    def test_unsubscribe(self):
        self.bus.subscribe(Event.LOGIN_FAILURE, self._handler)
        self.bus.unsubscribe(Event.LOGIN_FAILURE, self._handler)
        self.bus.publish(Event.LOGIN_FAILURE)

        self.assertEqual(len(self.received), 0)

    def test_publish_without_subscribers(self):
        """Publishing to an event with no subscribers should not error."""
        self.bus.publish(Event.DAEMON_START)

    def test_clear(self):
        self.bus.subscribe(Event.PORTAL_DETECTED, self._handler)
        self.bus.subscribe(Event.LOGIN_SUCCESS, self._handler)
        self.bus.clear()

        self.assertEqual(self.bus.subscriber_count, 0)

    def test_subscriber_count(self):
        self.bus.subscribe(Event.PORTAL_DETECTED, self._handler)
        self.bus.subscribe(Event.LOGIN_SUCCESS, self._handler)
        self.assertEqual(self.bus.subscriber_count, 2)

    def test_subscriber_exception_doesnt_break_others(self):
        """A failing subscriber should not prevent others from running."""
        results = []
        def bad_handler(**kwargs):
            raise RuntimeError("oops")
        def good_handler(**kwargs):
            results.append("ok")

        self.bus.subscribe(Event.SESSION_EXPIRED, bad_handler)
        self.bus.subscribe(Event.SESSION_EXPIRED, good_handler)
        self.bus.publish(Event.SESSION_EXPIRED)

        self.assertEqual(results, ["ok"])

    def test_events_are_isolated(self):
        """Subscribers only receive their subscribed events."""
        self.bus.subscribe(Event.PORTAL_DETECTED, self._handler)
        self.bus.publish(Event.LOGIN_SUCCESS)

        self.assertEqual(len(self.received), 0)


if __name__ == "__main__":
    unittest.main()
