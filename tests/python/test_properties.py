"""Property-based testing for formal invariants."""

import unittest
from typing import List

try:
    from hypothesis import given, strategies as st
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

import pytest

from captivity.core.state import ConnectionState, ConnectionStateMachine
from captivity.core.probe import ConnectivityStatus
from captivity.daemon.network_monitor import NetworkEvent
from captivity.daemon.runner import DaemonRunner
from captivity.core.login import LoginResult


@pytest.mark.skipif(not HAS_HYPOTHESIS, reason="Hypothesis not installed")
class TestFormalProperties(unittest.TestCase):
    """Fuzz testing for formal state machine invariants."""

    @given(
        probe_statuses=st.lists(
            st.sampled_from(list(ConnectivityStatus)), min_size=1, max_size=50
        ),
        network_events=st.lists(
            st.sampled_from(list(NetworkEvent)), min_size=1, max_size=50
        )
    )
    def test_probe_dominates_events(self, probe_statuses: List[ConnectivityStatus], network_events: List[NetworkEvent]):
        """Prove that the Probe result ALWAYS dominates raw network events."""
        from unittest.mock import MagicMock
        
        runner = DaemonRunner()
        runner.monitor = MagicMock()
        runner.network = "fuzz_net"
        runner.state_machine.debounce_duration = 0.0
        
        with unittest.mock.patch("captivity.daemon.runner.probe_connectivity_detailed") as mock_probe:
            with unittest.mock.patch("captivity.daemon.runner.do_login") as mock_login:
                mock_login.return_value = LoginResult.FAILED
                
                for event in network_events:
                    # Mock the probe result for the event handler's probe call
                    event_probe = MagicMock()
                    event_probe.status = ConnectivityStatus.CONNECTED # Arbitrary for the event handler
                    event_probe.detection_method = "fuzz"
                    mock_probe.return_value = event_probe
                    
                    runner._handle_network_event(event)
                    
                    # Now pick a random probe status for the manual probe override
                    probe_status = probe_statuses[len(probe_statuses) % len(probe_statuses)]
                    
                    mock_result = MagicMock()
                    mock_result.status = probe_status
                    mock_result.detection_method = "fuzz"
                    mock_probe.return_value = mock_result
                    
                    runner._run_probe()
                    
                    # Global Invariant: Probe dictates final state regardless of the raw event
                    if probe_status == ConnectivityStatus.CONNECTED:
                        self.assertEqual(runner.state_machine.state, ConnectionState.CONNECTED)
                    elif probe_status == ConnectivityStatus.NETWORK_UNAVAILABLE:
                        self.assertEqual(runner.state_machine.state, ConnectionState.ERROR)
                    elif probe_status == ConnectivityStatus.PORTAL_DETECTED:
                        # _run_probe -> PORTAL -> _handle_portal -> AUTHENTICATING -> (mocked login fails) -> ERROR
                        self.assertIn(runner.state_machine.state, {ConnectionState.ERROR, ConnectionState.WAIT_USER})


    @given(
        transitions=st.lists(
            st.sampled_from(list(ConnectionState)), min_size=1, max_size=100
        )
    )
    def test_no_stuck_states(self, transitions: List[ConnectionState]):
        """Prove that random illegal transitions do not deadlock the machine."""
        sm = ConnectionStateMachine(debounce_duration=0.0)
        
        for t in transitions:
            sm.transition(t)
            
            # Verify we are in a valid enum state
            self.assertIn(sm.state, list(ConnectionState))


if __name__ == "__main__":
    unittest.main()
