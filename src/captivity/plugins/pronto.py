"""
Pronto Networks captive portal plugin.

Handles login for Pronto Networks portals (the original v0.1 target).
Detects portals by checking for 'prontonetworks' in the response URL
or body content.
"""

import requests

from captivity.plugins.base import CaptivePortalPlugin
from captivity.utils.logging import get_logger

logger = get_logger("plugin.pronto")


class ProntoPlugin(CaptivePortalPlugin):
    """Plugin for Pronto Networks captive portals."""

    DEFAULT_ENDPOINT = "http://phc.prontonetworks.com/cgi-bin/authlogin"

    @property
    def name(self) -> str:
        return "Pronto Networks"

    @property
    def priority(self) -> int:
        """Built-in plugins have lower priority than user plugins."""
        return -10

    def detect(self, response: requests.Response) -> bool:
        """Detect Pronto Networks portal by URL or content."""
        url_match = "prontonetworks" in response.url.lower()
        content_match = "prontonetworks" in response.text.lower()
        return url_match or content_match

    def login(
        self,
        session: requests.Session,
        portal_url: str,
        username: str,
        password: str,
    ) -> bool:
        """Login using Pronto Networks form format."""
        login_data = {
            "userId": username,
            "password": password,
            "serviceName": "ProntoAuthentication",
            "Submit22": "Login",
        }

        endpoint = portal_url or self.DEFAULT_ENDPOINT

        try:
            logger.info("Submitting Pronto login to %s", endpoint)
            response = session.post(endpoint, data=login_data, timeout=10)
            logger.debug("Pronto response: HTTP %d", response.status_code)
            return response.status_code == 200
        except requests.exceptions.RequestException as exc:
            logger.error("Pronto login failed: %s", exc)
            return False
