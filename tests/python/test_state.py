"""Tests for captivity.core.state module."""

import unittest

from captivity.core.state import (
    ConnectionState,
    ConnectionStateMachine,
    InvalidTransition,
    VALID_TRANSITIONS,
)


class TestConnectionState(unittest.TestCase):
    """Test ConnectionState enum."""

    def test_all_states_defined(self):
        states = list(ConnectionState)
        self.assertEqual(len(states), 8)
        self.assertIn(ConnectionState.INIT, states)
        self.assertIn(ConnectionState.CONNECTED, states)

    def test_all_states_have_transitions(self):
        """Every state should have defined transitions."""
        for state in ConnectionState:
            self.assertIn(state, VALID_TRANSITIONS)


class TestConnectionStateMachine(unittest.TestCase):
    """Test ConnectionStateMachine."""

    def setUp(self):
        self.transitions = []
        def on_transition(old_state, new_state):
            self.transitions.append((old_state, new_state))
        self.sm = ConnectionStateMachine(on_transition=on_transition)

    def test_initial_state(self):
        self.assertEqual(self.sm.state, ConnectionState.INIT)

    def test_valid_transition(self):
        self.sm.transition(ConnectionState.NETWORK_CONNECTED)
        self.assertEqual(self.sm.state, ConnectionState.NETWORK_CONNECTED)
        self.assertEqual(self.sm.previous_state, ConnectionState.INIT)

    def test_invalid_transition_raises(self):
        """Cannot go directly from INIT to LOGGING_IN."""
        with self.assertRaises(InvalidTransition):
            self.sm.transition(ConnectionState.LOGGING_IN)

    def test_same_state_is_noop(self):
        """Transitioning to the same state is a no-op."""
        self.sm.transition(ConnectionState.CONNECTED)
        self.sm.transition(ConnectionState.CONNECTED)  # no error
        self.assertEqual(len(self.transitions), 1)

    def test_callback_invoked(self):
        self.sm.transition(ConnectionState.PORTAL_DETECTED)
        self.assertEqual(len(self.transitions), 1)
        self.assertEqual(
            self.transitions[0],
            (ConnectionState.INIT, ConnectionState.PORTAL_DETECTED),
        )

    def test_full_login_flow(self):
        """Test the typical login flow through states."""
        self.sm.transition(ConnectionState.PORTAL_DETECTED)
        self.sm.transition(ConnectionState.LOGGING_IN)
        self.sm.transition(ConnectionState.CONNECTED)
        self.assertEqual(self.sm.state, ConnectionState.CONNECTED)
        self.assertTrue(self.sm.is_connected)

    def test_session_expiry_flow(self):
        """Test session expiry and re-login flow."""
        self.sm.transition(ConnectionState.CONNECTED)
        self.sm.transition(ConnectionState.SESSION_EXPIRED)
        self.sm.transition(ConnectionState.PORTAL_DETECTED)
        self.sm.transition(ConnectionState.LOGGING_IN)
        self.sm.transition(ConnectionState.CONNECTED)
        self.assertTrue(self.sm.is_connected)

    def test_network_unavailable_recovery(self):
        """Test recovery from network unavailable."""
        self.sm.transition(ConnectionState.NETWORK_UNAVAILABLE)
        self.sm.transition(ConnectionState.NETWORK_CONNECTED)
        self.assertFalse(self.sm.needs_login)

    def test_needs_login(self):
        self.sm.transition(ConnectionState.PORTAL_DETECTED)
        self.assertTrue(self.sm.needs_login)

    def test_repr(self):
        self.assertIn("INIT", repr(self.sm))


if __name__ == "__main__":
    unittest.main()
