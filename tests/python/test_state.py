"""Tests for the strict ConnectionStateMachine."""

import unittest
from unittest.mock import patch

from captivity.core.state import (
    ConnectionState,
    ConnectionStateMachine,
    STATE_TIMEOUTS,
)


class TestConnectionStateMachine(unittest.TestCase):
    def setUp(self):
        self.transitions = []

        def on_transition(old_state, new_state):
            self.transitions.append((old_state, new_state))

        self.sm = ConnectionStateMachine(
            on_transition=on_transition, debounce_duration=0.0
        )

    def test_initial_state(self):
        self.assertEqual(self.sm.state, ConnectionState.INIT)
        self.assertFalse(self.sm.is_connected)

    def test_valid_transitions(self):
        # Normal flow
        self.sm.transition(ConnectionState.PROBING)
        self.assertEqual(self.sm.state, ConnectionState.PROBING)

        self.sm.transition(ConnectionState.PORTAL)
        self.assertEqual(self.sm.state, ConnectionState.PORTAL)

        self.sm.transition(ConnectionState.WAIT_USER)
        self.assertEqual(self.sm.state, ConnectionState.WAIT_USER)

        self.sm.transition(ConnectionState.CONNECTED)
        self.assertEqual(self.sm.state, ConnectionState.CONNECTED)
        self.assertTrue(self.sm.is_connected)

    def test_invalid_transition_forces_error(self):
        # INIT -> CONNECTED is invalid
        self.sm.transition(ConnectionState.CONNECTED)
        # Should force ERROR instead
        self.assertEqual(self.sm.state, ConnectionState.ERROR)

        # ERROR -> CONNECTED is invalid
        self.sm.transition(ConnectionState.CONNECTED)
        self.assertEqual(self.sm.state, ConnectionState.ERROR)

        # ERROR -> RETRY is valid
        self.sm.transition(ConnectionState.RETRY)
        self.assertEqual(self.sm.state, ConnectionState.RETRY)

    def test_watchdog_no_violation(self):
        self.sm.transition(ConnectionState.PROBING)
        with patch(
            "captivity.core.state.time.time", return_value=self.sm.state_entered_at + 1
        ):
            self.sm.check_watchdog()
        self.assertEqual(self.sm.state, ConnectionState.PROBING)

    def test_watchdog_violation_forces_transition(self):
        self.sm.transition(ConnectionState.PROBING)
        limit = STATE_TIMEOUTS[ConnectionState.PROBING]

        with patch(
            "captivity.core.state.time.time",
            return_value=self.sm.state_entered_at + limit + 1,
        ):
            self.sm.check_watchdog()

        # PROBING timeout should force ERROR
        self.assertEqual(self.sm.state, ConnectionState.ERROR)

    def test_watchdog_wait_user_timeout(self):
        self.sm.transition(ConnectionState.PROBING)
        self.sm.transition(ConnectionState.PORTAL)
        self.sm.transition(ConnectionState.WAIT_USER)

        limit = STATE_TIMEOUTS[ConnectionState.WAIT_USER]
        with patch(
            "captivity.core.state.time.time",
            return_value=self.sm.state_entered_at + limit + 1,
        ):
            self.sm.check_watchdog()

        # WAIT_USER timeout should force RETRY
        self.assertEqual(self.sm.state, ConnectionState.RETRY)

    def test_same_state_is_noop(self):
        self.sm.transition(ConnectionState.PROBING)
        self.transitions.clear()

        self.sm.transition(ConnectionState.PROBING)
        self.assertEqual(len(self.transitions), 0)


if __name__ == "__main__":
    unittest.main()
