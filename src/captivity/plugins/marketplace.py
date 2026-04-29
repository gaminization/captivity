"""
Plugin marketplace for discovering and installing portal plugins.

Provides:
  - Community plugin catalog (built-in known plugins)
  - Search by name, portal type, or keyword
  - Install via pip subprocess
  - Uninstall via pip subprocess
  - Local registry integration

The marketplace catalog is a built-in list of known community
plugins. Future versions may fetch from a remote registry.
"""

import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

from captivity.plugins.registry import PluginRegistry, PluginEntry
from captivity.utils.logging import get_logger

logger = get_logger("plugin.marketplace")


@dataclass
class MarketplacePlugin:
    """A plugin available in the marketplace catalog.

    Attributes:
        package: pip package name.
        name: Human-readable name.
        description: Short description.
        portal_types: Portal types this plugin handles.
        author: Plugin author.
        version: Latest known version.
        url: Project/repository URL.
    """

    package: str
    name: str
    description: str = ""
    portal_types: list[str] = field(default_factory=list)
    author: str = ""
    version: str = "0.0.0"
    url: str = ""


# Built-in catalog of known community plugins.
# In the future this could be fetched from a remote API.
CATALOG: dict[str, MarketplacePlugin] = {
    "captivity-plugin-cisco": MarketplacePlugin(
        package="captivity-plugin-cisco",
        name="Cisco Web Auth",
        description="Plugin for Cisco WLC web authentication portals",
        portal_types=["cisco", "cisco-wlc"],
        author="Captivity Community",
        version="0.1.0",
        url="https://github.com/captivity-plugins/cisco",
    ),
    "captivity-plugin-aruba": MarketplacePlugin(
        package="captivity-plugin-aruba",
        name="Aruba ClearPass",
        description="Plugin for Aruba ClearPass captive portals",
        portal_types=["aruba", "clearpass"],
        author="Captivity Community",
        version="0.1.0",
        url="https://github.com/captivity-plugins/aruba",
    ),
    "captivity-plugin-coovachilli": MarketplacePlugin(
        package="captivity-plugin-coovachilli",
        name="CoovaChilli",
        description="Plugin for CoovaChilli/ChilliSpot hotspot portals",
        portal_types=["coovachilli", "chillispot"],
        author="Captivity Community",
        version="0.1.0",
        url="https://github.com/captivity-plugins/coovachilli",
    ),
    "captivity-plugin-fortinet": MarketplacePlugin(
        package="captivity-plugin-fortinet",
        name="Fortinet FortiGate",
        description="Plugin for Fortinet FortiGate captive portals",
        portal_types=["fortinet", "fortigate"],
        author="Captivity Community",
        version="0.1.0",
        url="https://github.com/captivity-plugins/fortinet",
    ),
    "captivity-plugin-mikrotik": MarketplacePlugin(
        package="captivity-plugin-mikrotik",
        name="MikroTik Hotspot",
        description="Plugin for MikroTik RouterOS hotspot portals",
        portal_types=["mikrotik", "routeros"],
        author="Captivity Community",
        version="0.1.0",
        url="https://github.com/captivity-plugins/mikrotik",
    ),
    "captivity-plugin-unifi": MarketplacePlugin(
        package="captivity-plugin-unifi",
        name="UniFi Guest Portal",
        description="Plugin for Ubiquiti UniFi guest portals",
        portal_types=["unifi", "ubiquiti"],
        author="Captivity Community",
        version="0.1.0",
        url="https://github.com/captivity-plugins/unifi",
    ),
}


class Marketplace:
    """Plugin marketplace for searching, installing, and managing plugins.

    Attributes:
        registry: Local plugin registry instance.
    """

    def __init__(self, registry: Optional[PluginRegistry] = None) -> None:
        self.registry = registry or PluginRegistry()

    def search(self, query: str = "") -> list[MarketplacePlugin]:
        """Search the plugin catalog.

        Args:
            query: Search string (matches name, package, description,
                   or portal types). Empty string returns all plugins.

        Returns:
            List of matching marketplace plugins.
        """
        if not query:
            return list(CATALOG.values())

        query_lower = query.lower()
        results = []
        for plugin in CATALOG.values():
            searchable = " ".join(
                [
                    plugin.package,
                    plugin.name,
                    plugin.description,
                    " ".join(plugin.portal_types),
                ]
            ).lower()
            if query_lower in searchable:
                results.append(plugin)
        return results

    def install(self, package: str) -> tuple[bool, str]:
        """Install a plugin via pip.

        Args:
            package: pip package name to install.

        Returns:
            Tuple of (success, message).
        """
        if self.registry.is_installed(package):
            return False, f"Plugin {package} is already installed"

        logger.info("Installing plugin: %s", package)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                msg = f"pip install failed: {result.stderr.strip()}"
                logger.error(msg)
                return False, msg

            # Get version from catalog or default
            catalog_info = CATALOG.get(package)
            version = catalog_info.version if catalog_info else "unknown"
            description = catalog_info.description if catalog_info else ""
            name = catalog_info.name if catalog_info else package
            portal_types = catalog_info.portal_types if catalog_info else []

            # Try to get actual installed version
            try:
                from importlib.metadata import version as get_version

                version = get_version(package)
            except Exception:
                pass

            entry = PluginEntry(
                package=package,
                name=name,
                version=version,
                description=description,
                source="pypi",
                portal_types=portal_types,
            )
            self.registry.register(entry)
            return True, f"Installed {package} v{version}"

        except subprocess.TimeoutExpired:
            return False, "Installation timed out"
        except Exception as exc:
            return False, f"Installation error: {exc}"

    def uninstall(self, package: str) -> tuple[bool, str]:
        """Uninstall a plugin via pip.

        Args:
            package: pip package name to uninstall.

        Returns:
            Tuple of (success, message).
        """
        if not self.registry.is_installed(package):
            return False, f"Plugin {package} is not installed"

        logger.info("Uninstalling plugin: %s", package)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "-y", package],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                msg = f"pip uninstall failed: {result.stderr.strip()}"
                logger.error(msg)
                return False, msg

            self.registry.unregister(package)
            return True, f"Uninstalled {package}"

        except subprocess.TimeoutExpired:
            return False, "Uninstall timed out"
        except Exception as exc:
            return False, f"Uninstall error: {exc}"

    def get_info(self, package: str) -> Optional[MarketplacePlugin]:
        """Get catalog info for a plugin.

        Args:
            package: pip package name.

        Returns:
            MarketplacePlugin if found in catalog, None otherwise.
        """
        return CATALOG.get(package)

    def list_installed(self) -> list[PluginEntry]:
        """List all installed marketplace plugins."""
        return self.registry.list_plugins()

    def __repr__(self) -> str:
        installed = self.registry.count
        available = len(CATALOG)
        return f"Marketplace(installed={installed}, catalog={available})"
