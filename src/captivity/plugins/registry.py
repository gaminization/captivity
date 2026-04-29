"""
Local plugin registry for tracking installed marketplace plugins.

Stores metadata about installed plugins in a JSON file:
  - package name, version, description
  - install timestamp
  - source (pypi, local, url)

Uses XDG_DATA_HOME for storage, consistent with other Captivity data.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from captivity.utils.logging import get_logger

logger = get_logger("plugin.registry")


def _registry_path() -> Path:
    """Get the path to the plugin registry file."""
    import os

    base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    path = Path(base) / "captivity" / "plugins"
    path.mkdir(parents=True, exist_ok=True)
    return path / "registry.json"


@dataclass
class PluginEntry:
    """Registry entry for an installed plugin.

    Attributes:
        package: pip package name (e.g. 'captivity-plugin-cisco').
        name: Human-readable plugin name.
        version: Installed version string.
        description: Short description.
        source: Installation source ('pypi', 'local', 'url').
        installed_at: Unix timestamp of installation.
        portal_types: List of portal types this plugin handles.
    """

    package: str
    name: str
    version: str = "0.0.0"
    description: str = ""
    source: str = "pypi"
    installed_at: float = field(default_factory=time.time)
    portal_types: list[str] = field(default_factory=list)


class PluginRegistry:
    """Manages the local registry of installed marketplace plugins.

    The registry is a JSON file tracking which plugins have been
    installed via the marketplace, separate from built-in plugins.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or _registry_path()
        self._entries: dict[str, PluginEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        if not self._path.exists():
            self._entries = {}
            return
        try:
            data = json.loads(self._path.read_text())
            self._entries = {}
            for pkg, entry_data in data.items():
                self._entries[pkg] = PluginEntry(**entry_data)
            logger.debug("Loaded %d registry entries", len(self._entries))
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            logger.warning("Corrupt registry file, resetting: %s", exc)
            self._entries = {}

    def _save(self) -> None:
        """Persist registry to disk."""
        data = {pkg: asdict(entry) for pkg, entry in self._entries.items()}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2))

    def register(self, entry: PluginEntry) -> None:
        """Register an installed plugin."""
        self._entries[entry.package] = entry
        self._save()
        logger.info("Registered plugin: %s v%s", entry.package, entry.version)

    def unregister(self, package: str) -> bool:
        """Remove a plugin from the registry.

        Returns:
            True if the plugin was found and removed.
        """
        if package in self._entries:
            del self._entries[package]
            self._save()
            logger.info("Unregistered plugin: %s", package)
            return True
        return False

    def get(self, package: str) -> Optional[PluginEntry]:
        """Get a plugin entry by package name."""
        return self._entries.get(package)

    def list_plugins(self) -> list[PluginEntry]:
        """List all registered plugins."""
        return list(self._entries.values())

    def is_installed(self, package: str) -> bool:
        """Check if a plugin is registered."""
        return package in self._entries

    @property
    def count(self) -> int:
        """Number of registered plugins."""
        return len(self._entries)

    def __repr__(self) -> str:
        return f"PluginRegistry(count={self.count})"
