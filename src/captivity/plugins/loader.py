"""
Plugin discovery and loading.

Finds plugins via:
    1. Built-in plugins (pronto, generic)
    2. Entry points: 'captivity.plugins' group (pip-installable)
    3. Directory scan (future: user plugin directory)

Plugins are sorted by priority (highest first) and selected
based on their detect() method.
"""

import importlib
from typing import Optional

import requests

from captivity.plugins.base import CaptivePortalPlugin
from captivity.utils.logging import get_logger

logger = get_logger("plugin.loader")


# Built-in plugins (lazy-loaded to avoid circular imports)
_BUILTIN_PLUGINS = [
    "captivity.plugins.pronto:ProntoPlugin",
    "captivity.plugins.generic:GenericPlugin",
]


def _load_class(dotted_path: str) -> type:
    """Load a class from a dotted path like 'module:ClassName'."""
    module_path, class_name = dotted_path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def discover_plugins() -> list[CaptivePortalPlugin]:
    """Discover and instantiate all available plugins.

    Loads plugins from:
        1. Built-in plugins
        2. Entry points (if importlib.metadata available)

    Returns:
        List of plugin instances sorted by priority (highest first).
    """
    plugins = []

    # Load built-in plugins
    for path in _BUILTIN_PLUGINS:
        try:
            cls = _load_class(path)
            plugins.append(cls())
            logger.debug("Loaded built-in plugin: %s", path)
        except Exception as exc:
            logger.warning("Failed to load built-in plugin %s: %s", path, exc)

    # Load entry point plugins
    try:
        from importlib.metadata import entry_points

        eps = entry_points()
        # Python 3.12+ returns a SelectableGroups, 3.9+ returns dict
        if hasattr(eps, "select"):
            captivity_eps = eps.select(group="captivity.plugins")
        elif isinstance(eps, dict):
            captivity_eps = eps.get("captivity.plugins", [])
        else:
            captivity_eps = []

        for ep in captivity_eps:
            try:
                cls = ep.load()
                plugin = cls()
                if isinstance(plugin, CaptivePortalPlugin):
                    plugins.append(plugin)
                    logger.info("Loaded plugin from entry point: %s", ep.name)
            except Exception as exc:
                logger.warning("Failed to load plugin %s: %s", ep.name, exc)

    except ImportError:
        logger.debug("importlib.metadata not available, skipping entry points")

    # Sort by priority (highest first)
    plugins.sort(key=lambda p: p.priority, reverse=True)

    logger.info(
        "Discovered %d plugins: %s",
        len(plugins),
        ", ".join(p.name for p in plugins),
    )

    return plugins


def select_plugin(
    response: requests.Response,
    plugins: Optional[list[CaptivePortalPlugin]] = None,
) -> Optional[CaptivePortalPlugin]:
    """Select the best plugin for a portal response.

    Iterates through plugins in priority order and returns the
    first one whose detect() method returns True.

    Args:
        response: HTTP response from the portal page.
        plugins: Optional list of plugins (auto-discovers if None).

    Returns:
        The matching plugin, or None.
    """
    if plugins is None:
        plugins = discover_plugins()

    for plugin in plugins:
        try:
            if plugin.detect(response):
                logger.info("Selected plugin: %s", plugin.name)
                return plugin
        except Exception as exc:
            logger.warning(
                "Plugin %s detection error: %s",
                plugin.name,
                exc,
            )

    logger.warning("No plugin matched the portal response")
    return None
