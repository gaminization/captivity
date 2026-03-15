"""
Captive portal login engine.

Handles the login flow for captive portals using a requests session:
  1. Retrieve credentials from secure storage
  2. Trigger the portal (get cookies)
  3. Submit login form
  4. Verify connectivity
"""

from typing import Optional

import requests

from captivity.core.credentials import retrieve, CredentialError
from captivity.core.probe import probe_connectivity, ConnectivityStatus
from captivity.utils.logging import get_logger

logger = get_logger("login")

# Default Pronto Networks portal endpoint
DEFAULT_PORTAL = "http://phc.prontonetworks.com/cgi-bin/authlogin"


class LoginError(Exception):
    """Raised when login fails."""


def do_login(
    network: str,
    portal_url: str = DEFAULT_PORTAL,
    dry_run: bool = False,
) -> bool:
    """Perform a captive portal login.

    Retrieves stored credentials for the network, triggers the portal
    to obtain session cookies, submits the login form, and verifies
    internet connectivity.

    Args:
        network: Network name for credential lookup.
        portal_url: Portal login endpoint URL.
        dry_run: If True, log actions without making requests.

    Returns:
        True if login succeeded (connectivity verified), False otherwise.

    Raises:
        CredentialError: If credentials cannot be retrieved.
        LoginError: If login request fails.
    """
    logger.info("Starting login for network '%s' via %s", network, portal_url)

    # Step 1: Retrieve credentials
    try:
        username, password = retrieve(network)
    except CredentialError as exc:
        logger.error("Credential retrieval failed: %s", exc)
        raise

    if dry_run:
        logger.info("[DRY-RUN] Would trigger portal: %s", portal_url)
        logger.info("[DRY-RUN] Would submit login as: %s", username)
        logger.info("[DRY-RUN] Would verify connectivity")
        return True

    session = requests.Session()

    # Step 2: Trigger portal (get cookies)
    try:
        logger.debug("Triggering portal at %s", portal_url)
        session.get(portal_url, timeout=10)
    except requests.exceptions.RequestException as exc:
        raise LoginError(f"Failed to reach portal: {exc}") from exc

    # Step 3: Submit login form (Pronto Networks format)
    login_data = {
        "userId": username,
        "password": password,
        "serviceName": "ProntoAuthentication",
        "Submit22": "Login",
    }

    try:
        logger.debug("Submitting login credentials")
        response = session.post(portal_url, data=login_data, timeout=10)
        logger.debug("Login response: HTTP %d", response.status_code)
    except requests.exceptions.RequestException as exc:
        raise LoginError(f"Login submission failed: {exc}") from exc

    # Step 4: Verify connectivity
    status, _ = probe_connectivity()

    if status == ConnectivityStatus.CONNECTED:
        logger.info("Login successful — internet connectivity verified")
        return True
    else:
        logger.warning(
            "Login submitted but connectivity not verified (status: %s)",
            status.value,
        )
        return False
