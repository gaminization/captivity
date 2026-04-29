"""Stress test for the ConnectionStateMachine."""

import unittest
from captivity.core.state import ConnectionState, ConnectionStateMachine


class TestStateMachineStress(unittest.TestCase):
    def test_full_login_cycle(self):
        sm = ConnectionStateMachine(debounce_duration=0.0)
        sm.transition(ConnectionState.PROBING)
        sm.transition(ConnectionState.PORTAL)
        sm.transition(ConnectionState.WAIT_USER)
        sm.transition(ConnectionState.CONNECTED)
        self.assertTrue(sm.is_connected)

    def test_network_disconnect_recovery(self):
        sm = ConnectionStateMachine(debounce_duration=0.0)
        sm.transition(ConnectionState.PROBING)
        sm.transition(ConnectionState.CONNECTED)

        # Disconnect -> PROBING
        sm.transition(ConnectionState.PROBING)
        sm.transition(ConnectionState.ERROR)
        sm.transition(ConnectionState.RETRY)
        sm.transition(ConnectionState.PROBING)
        sm.transition(ConnectionState.CONNECTED)
        self.assertTrue(sm.is_connected)

    def test_invalid_transition_forces_error(self):
        sm = ConnectionStateMachine()
        # Invalid
        sm.transition(ConnectionState.CONNECTED)
        self.assertEqual(sm.state, ConnectionState.ERROR)

    def test_stress_100_transitions(self):
        sm = ConnectionStateMachine(debounce_duration=0.0)
        for _ in range(25):
            sm.transition(ConnectionState.PROBING)
            sm.transition(ConnectionState.PORTAL)
            sm.transition(ConnectionState.WAIT_USER)
            sm.transition(ConnectionState.CONNECTED)
        self.assertTrue(sm.is_connected)


if __name__ == "__main__":
    unittest.main()
