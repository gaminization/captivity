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
from pathlib import Path
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


def _user_plugin_dir() -> Path:
    """Get the user plugin directory."""
    import os

    base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return Path(base) / "captivity" / "plugins"


def _load_user_plugins() -> list[CaptivePortalPlugin]:
    """Scan user plugin directory for plugin classes.

    Looks for .py files in ~/.local/share/captivity/plugins/ that
    contain classes inheriting from CaptivePortalPlugin.

    Returns:
        List of instantiated user plugin instances.
    """
    plugin_dir = _user_plugin_dir()
    plugins: list[CaptivePortalPlugin] = []

    if not plugin_dir.is_dir():
        return plugins

    import importlib.util

    for py_file in sorted(plugin_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue

        module_name = f"captivity_user_plugin_{py_file.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, CaptivePortalPlugin)
                    and attr is not CaptivePortalPlugin
                ):
                    plugin = attr()
                    plugins.append(plugin)
                    logger.info("Loaded user plugin: %s from %s", plugin.name, py_file.name)

        except Exception as exc:
            logger.warning("Failed to load user plugin %s: %s", py_file.name, exc)

    return plugins


def discover_plugins() -> list[CaptivePortalPlugin]:
    """Discover and instantiate all available plugins.

    Loads plugins from:
        1. Built-in plugins
        2. Entry points (if importlib.metadata available)
        3. User plugin directory (~/.local/share/captivity/plugins/)

    Calls on_load() on each plugin and skips plugins that fail validate().

    Returns:
        List of plugin instances sorted by priority (highest first).
    """
    plugins = []

    # Layer 1: Load built-in plugins
    for path in _BUILTIN_PLUGINS:
        try:
            cls = _load_class(path)
            plugins.append(cls())
            logger.debug("Loaded built-in plugin: %s", path)
        except Exception as exc:
            logger.warning("Failed to load built-in plugin %s: %s", path, exc)

    # Layer 2: Load entry point plugins
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

    # Layer 3: Load user plugins from directory
    plugins.extend(_load_user_plugins())

    # Lifecycle: call on_load() and validate()
    validated = []
    for plugin in plugins:
        try:
            plugin.on_load()
        except Exception as exc:
            logger.warning("Plugin %s on_load() failed: %s", plugin.name, exc)

        try:
            if plugin.validate():
                validated.append(plugin)
            else:
                logger.warning("Plugin %s failed validation, skipping", plugin.name)
        except Exception as exc:
            logger.warning("Plugin %s validate() error: %s", plugin.name, exc)

    # Sort by priority (highest first)
    validated.sort(key=lambda p: p.priority, reverse=True)

    logger.info(
        "Discovered %d plugins: %s",
        len(validated),
        ", ".join(p.name for p in validated),
    )

    return validated


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
