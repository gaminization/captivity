import pytest
import tempfile
import pathlib

@pytest.fixture(autouse=True)
def mock_data_dir(monkeypatch):
    """Ensure tests never write to the user's actual data directory."""
    temp_dir = tempfile.TemporaryDirectory()
    temp_path = pathlib.Path(temp_dir.name)
    
    # Patch the global paths to point to temp dir
    monkeypatch.setattr("captivity.telemetry.stats.STATS_DIR", temp_path)
    monkeypatch.setattr("captivity.telemetry.stats.STATS_FILE", temp_path / "stats.json")
    monkeypatch.setattr("captivity.core.cache.CACHE_FILE", temp_path / "portal_cache.json")
    monkeypatch.setattr("captivity.core.profiles.PROFILES_FILE", temp_path / "profiles.json")
    
    yield temp_path
    
    temp_dir.cleanup()
