"""
Plugin system for captive portal support.

Provides:
    - CaptivePortalPlugin: abstract base class for portal plugins
    - Built-in plugins: pronto, generic
    - Plugin discovery via entry_points and directory scanning
"""

from captivity.plugins.base import CaptivePortalPlugin

__all__ = ["CaptivePortalPlugin"]
