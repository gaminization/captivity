"""
Integration test: State machine stress.

Tests rapid state transitions, history tracking,
and invariant validation under stress.
"""

from captivity.core.state import (
    ConnectionState,
    ConnectionStateMachine,
    InvalidTransition,
    VALID_TRANSITIONS,
)


class TestStateMachineStress:
    """Stress test the connection state machine."""

    def test_full_login_cycle(self):
        """Complete login flow should work without errors."""
        sm = ConnectionStateMachine()
        assert sm.state == ConnectionState.INIT

        sm.transition(ConnectionState.NETWORK_CONNECTED)
        assert sm.state == ConnectionState.NETWORK_CONNECTED

        sm.transition(ConnectionState.PORTAL_DETECTED)
        assert sm.state == ConnectionState.PORTAL_DETECTED

        sm.transition(ConnectionState.LOGGING_IN)
        assert sm.state == ConnectionState.LOGGING_IN

        sm.transition(ConnectionState.CONNECTED)
        assert sm.state == ConnectionState.CONNECTED

    def test_session_expiry_recovery(self):
        """Session expiry → re-login should work."""
        sm = ConnectionStateMachine()
        sm.transition(ConnectionState.NETWORK_CONNECTED)
        sm.transition(ConnectionState.CONNECTED)
        sm.transition(ConnectionState.SESSION_EXPIRED)
        sm.transition(ConnectionState.PORTAL_DETECTED)
        sm.transition(ConnectionState.LOGGING_IN)
        sm.transition(ConnectionState.CONNECTED)
        assert sm.state == ConnectionState.CONNECTED

    def test_rapid_transitions(self):
        """Rapid valid transitions should all complete."""
        sm = ConnectionStateMachine()
        sequence = [
            ConnectionState.NETWORK_CONNECTED,
            ConnectionState.PORTAL_DETECTED,
            ConnectionState.LOGGING_IN,
            ConnectionState.CONNECTED,
            ConnectionState.SESSION_EXPIRED,
            ConnectionState.PORTAL_DETECTED,
            ConnectionState.LOGGING_IN,
            ConnectionState.RETRY_WAIT,
            ConnectionState.LOGGING_IN,
            ConnectionState.CONNECTED,
        ]
        for state in sequence:
            sm.transition(state)
        assert sm.state == ConnectionState.CONNECTED
        assert len(sm.history) == len(sequence)

    def test_invalid_transition_raises(self):
        """Invalid transitions should raise InvalidTransition."""
        sm = ConnectionStateMachine()
        # INIT → LOGGING_IN is not valid
        raised = False
        try:
            sm.transition(ConnectionState.LOGGING_IN)
        except InvalidTransition:
            raised = True
        assert raised, "Should have raised InvalidTransition"

    def test_same_state_noop(self):
        """Transitioning to the same state should be a no-op."""
        sm = ConnectionStateMachine()
        sm.transition(ConnectionState.NETWORK_CONNECTED)
        history_len = len(sm.history)
        sm.transition(ConnectionState.NETWORK_CONNECTED)
        assert len(sm.history) == history_len  # No new history entry

    def test_history_tracks_all_transitions(self):
        """History should track every transition."""
        sm = ConnectionStateMachine()
        sm.transition(ConnectionState.NETWORK_CONNECTED)
        sm.transition(ConnectionState.PORTAL_DETECTED)
        sm.transition(ConnectionState.LOGGING_IN)
        sm.transition(ConnectionState.CONNECTED)
        assert len(sm.history) == 4
        assert sm.history[0].from_state == ConnectionState.INIT
        assert sm.history[0].to_state == ConnectionState.NETWORK_CONNECTED
        assert sm.history[-1].to_state == ConnectionState.CONNECTED

    def test_all_states_are_reachable(self):
        """Every state should be reachable from some other state."""
        reachable = set()
        for from_state, to_states in VALID_TRANSITIONS.items():
            reachable.add(from_state)
            reachable.update(to_states)
        for state in ConnectionState:
            assert state in reachable, f"{state} is not reachable"

    def test_network_disconnect_recovery(self):
        """Full disconnect → connect cycle."""
        sm = ConnectionStateMachine()
        sm.transition(ConnectionState.NETWORK_CONNECTED)
        sm.transition(ConnectionState.CONNECTED)
        sm.transition(ConnectionState.NETWORK_UNAVAILABLE)
        sm.transition(ConnectionState.NETWORK_CONNECTED)
        sm.transition(ConnectionState.CONNECTED)
        assert sm.state == ConnectionState.CONNECTED

    def test_stress_100_transitions(self):
        """100 transitions should work without error."""
        sm = ConnectionStateMachine()
        # Use a cycle that follows valid transitions
        cycle = [
            ConnectionState.NETWORK_CONNECTED,
            ConnectionState.PORTAL_DETECTED,
            ConnectionState.LOGGING_IN,
            ConnectionState.CONNECTED,
            ConnectionState.NETWORK_UNAVAILABLE,  # SESSION_EXPIRED can't go to NETWORK_CONNECTED
        ]
        for i in range(20):
            for state in cycle:
                sm.transition(state)
        assert sm.state == ConnectionState.NETWORK_UNAVAILABLE
        assert len(sm.history) == 100

    def test_callback_fires_on_transition(self):
        """on_transition callback should fire for each transition."""
        calls = []
        sm = ConnectionStateMachine(
            on_transition=lambda old_state, new_state, **kw: calls.append((old_state, new_state))
        )
        sm.transition(ConnectionState.NETWORK_CONNECTED)
        sm.transition(ConnectionState.CONNECTED)
        assert len(calls) == 2
        assert calls[0] == (ConnectionState.INIT, ConnectionState.NETWORK_CONNECTED)
        assert calls[1] == (ConnectionState.NETWORK_CONNECTED, ConnectionState.CONNECTED)
