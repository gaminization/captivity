"""
Abstract base class for captive portal plugins.

Each plugin must implement:
    - detect(response) → bool: whether this plugin handles the portal
    - login(session, portal_url, username, password) → bool: perform login
    - name (property): human-readable plugin name
    - priority (property): selection priority (higher = checked first)
"""

from abc import ABC, abstractmethod
from typing import Optional

import requests


class CaptivePortalPlugin(ABC):
    """Base class for captive portal login plugins.

    Plugins are selected based on their `detect()` method, which
    examines the portal response to determine if the plugin can
    handle the login. The plugin with the highest priority that
    detects the portal is used.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable plugin name."""

    @property
    def priority(self) -> int:
        """Plugin selection priority (higher = checked first).

        Default is 0. Built-in plugins use negative priorities
        so user plugins are always checked first.
        """
        return 0

    @abstractmethod
    def detect(self, response: requests.Response) -> bool:
        """Check if this plugin can handle the given portal.

        Args:
            response: HTTP response from the portal page.

        Returns:
            True if this plugin can handle the portal.
        """

    @abstractmethod
    def login(
        self,
        session: requests.Session,
        portal_url: str,
        username: str,
        password: str,
    ) -> bool:
        """Perform the login to the captive portal.

        Args:
            session: Requests session (with cookies from portal).
            portal_url: URL of the portal login page.
            username: Login username.
            password: Login password.

        Returns:
            True if login was successful.
        """
