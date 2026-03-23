"""
Testing utilities for Captivity.

Provides a captive portal simulator for plugin development
and integration testing without requiring real networks.
"""

from captivity.testing.simulator import PortalSimulator
from captivity.testing.scenarios import SCENARIOS, Scenario

__all__ = ["PortalSimulator", "SCENARIOS", "Scenario"]
