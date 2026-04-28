"""
Integration test: Live connectivity probe.

Tests the real HTTP 204 probe against Google's connectivity
check endpoint. Requires actual internet access.
"""

import pytest
import requests

from captivity.core.probe import probe_connectivity, ConnectivityStatus


class TestLiveProbe:
    """Test real connectivity probing."""

    def test_probe_returns_valid_status(self):
        """Probe should return a valid ConnectivityStatus."""
        status, redirect_url = probe_connectivity()
        assert isinstance(status, ConnectivityStatus)

    def test_probe_connected_when_internet_available(self):
        """When internet is available, probe should return CONNECTED."""
        # First verify we actually have internet
        try:
            r = requests.get("https://clients3.google.com/generate_204", timeout=5)
            has_internet = r.status_code == 204
        except Exception:
            has_internet = False

        if not has_internet:
            pytest.skip("No internet — cannot test live probe")

        status, redirect_url = probe_connectivity()
        assert status == ConnectivityStatus.CONNECTED
        assert redirect_url is None or redirect_url == ""

    def test_probe_is_fast(self):
        """Probe should complete within 10 seconds."""
        import time
        start = time.time()
        probe_connectivity()
        elapsed = time.time() - start
        assert elapsed < 10.0, f"Probe took {elapsed:.1f}s (max 10s)"

    def test_multiple_probes_consistent(self):
        """Multiple probes should return the same status."""
        results = [probe_connectivity()[0] for _ in range(3)]
        assert all(r == results[0] for r in results), (
            f"Inconsistent probe results: {results}"
        )
