"""
Generic captive portal plugin.

Uses the HTML form parser from v0.7 to handle arbitrary captive
portals. This is the fallback plugin when no specific plugin matches.
"""

import requests

from captivity.plugins.base import CaptivePortalPlugin
from captivity.core.parser import parse_portal_page
from captivity.utils.logging import get_logger

logger = get_logger("plugin.generic")


class GenericPlugin(CaptivePortalPlugin):
    """Generic plugin using dynamic form parsing."""

    @property
    def name(self) -> str:
        return "Generic (form parser)"

    @property
    def priority(self) -> int:
        """Lowest priority — used as fallback."""
        return -100

    def detect(self, response: requests.Response) -> bool:
        """Always returns True — this is the fallback plugin.

        The generic plugin can attempt login on any portal that
        contains an HTML form with username/password fields.
        """
        return "<form" in response.text.lower()

    def login(
        self,
        session: requests.Session,
        portal_url: str,
        username: str,
        password: str,
    ) -> bool:
        """Login by parsing the portal form and submitting credentials."""
        form = parse_portal_page(portal_url)

        if not form:
            logger.warning("No login form found at %s", portal_url)
            return False

        if not form.username_field or not form.password_field:
            logger.warning(
                "Form found but missing credential fields at %s",
                portal_url,
            )
            return False

        payload = form.build_payload(username, password)

        try:
            logger.info("Submitting generic login to %s", form.action)
            response = session.post(
                form.action,
                data=payload,
                timeout=10,
            )
            logger.debug("Generic response: HTTP %d", response.status_code)
            return response.status_code == 200
        except requests.exceptions.RequestException as exc:
            logger.error("Generic login failed: %s", exc)
            return False
