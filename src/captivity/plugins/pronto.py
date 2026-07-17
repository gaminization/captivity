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
        """Login using deterministic Pronto Networks form format."""

        # Hardcoded endpoint matching v0.1 bash script
        LOGIN_URL = "http://phc.prontonetworks.com/cgi-bin/authlogin"
        REDIRECT = "http://detectportal.firefox.com/canonical.html"

        try:
            # 1. STEP=TRIGGER_PORTAL
            logger.debug("STEP=TRIGGER_PORTAL")
            trigger_url = f"{LOGIN_URL}?URI={REDIRECT}"
            logger.info("Initializing Pronto session: %s", trigger_url)
            session.get(trigger_url, timeout=10)

            # 2. STEP=SUBMIT_LOGIN
            logger.debug("STEP=SUBMIT_LOGIN")
            payload = {
                "userId": username,
                "password": password,
                "serviceName": "ProntoAuthentication",
                "Submit22": "Login",
            }

            logger.info("Submitting Pronto POST payload to %s", LOGIN_URL)
            post_response = session.post(
                LOGIN_URL, data=payload, allow_redirects=True, timeout=15
            )

            logger.debug("Pronto POST response: HTTP %d", post_response.status_code)

            # 3. STEP=VERIFY_CONNECTIVITY
            logger.debug("STEP=VERIFY_CONNECTIVITY")
            logger.info("Verifying connectivity post-login...")
            verify_response = session.get(REDIRECT, timeout=5, allow_redirects=False)

            # Check Firefox captive portal success condition
            if (
                verify_response.status_code == 200
                and "success" in verify_response.text.lower()
            ):
                logger.info("Pronto login successful: Firefox canonical verified")
                return True

            # Fallback to standard 204 check
            probe_204 = session.get(
                "http://clients3.google.com/generate_204",
                timeout=5,
                allow_redirects=False,
            )
            if probe_204.status_code == 204:
                logger.info("Pronto login successful: HTTP 204 verified")
                return True

            logger.error(
                "Pronto login failed: Verification returned HTTP %d (canonical) / HTTP %d (204)",
                verify_response.status_code,
                probe_204.status_code,
            )
            return False

        except requests.exceptions.RequestException as exc:
            logger.error("Pronto login failed due to network error: %s", exc)
            return False
