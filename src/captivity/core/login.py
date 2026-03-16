"""
Captive portal login engine.

Performs the full login flow:
  1. Check portal cache for fast-path login
  2. Retrieve credentials from secure storage
  3. Probe connectivity to detect portal
  4. Select matching plugin via portal detection
  5. Execute plugin login
  6. Cache successful endpoint for future fast-path
  7. Verify connectivity

Integrates: plugins, parser, cache, credentials, probe.
"""

from typing import Optional

import requests

from captivity.core.credentials import retrieve, CredentialError
from captivity.core.probe import probe_connectivity, ConnectivityStatus
from captivity.core.cache import PortalCache, CacheEntry
from captivity.plugins.loader import discover_plugins, select_plugin
from captivity.utils.logging import get_logger

logger = get_logger("login")


class LoginError(Exception):
    """Raised when login fails."""


def do_login(
    network: str,
    portal_url: Optional[str] = None,
    dry_run: bool = False,
) -> bool:
    """Perform a captive portal login using the plugin system.

    Flow:
        1. Retrieve stored credentials
        2. Try cached endpoint (fast path) if available
        3. If no cache hit, probe for portal and use plugin detection
        4. Cache endpoint on success
        5. Verify connectivity

    Args:
        network: Network name for credential lookup.
        portal_url: Optional portal URL override.
        dry_run: If True, log actions without making requests.

    Returns:
        True if login succeeded (connectivity verified), False otherwise.

    Raises:
        CredentialError: If credentials cannot be retrieved.
        LoginError: If login request fails.
    """
    logger.info("Starting login for network '%s'", network)

    # Step 1: Retrieve credentials
    try:
        username, password = retrieve(network)
    except CredentialError as exc:
        logger.error("Credential retrieval failed: %s", exc)
        raise

    if dry_run:
        logger.info("[DRY-RUN] Would login as: %s", username)
        return True

    session = requests.Session()
    cache = PortalCache()

    # Step 2: Try cached endpoint (fast path)
    cached = cache.get(network)
    if cached and not portal_url:
        logger.info("Using cached endpoint: %s", cached.login_endpoint)
        success = _login_via_cache(session, cached, username, password)
        if success:
            return _verify_login()
        else:
            logger.info("Cached login failed, falling back to full flow")
            cache.remove(network)

    # Step 3: Detect portal
    actual_portal_url = portal_url
    if not actual_portal_url:
        _, redirect_url = probe_connectivity()
        if redirect_url:
            actual_portal_url = redirect_url
        else:
            logger.warning("No portal redirect detected")
            return False

    # Step 4: Fetch portal page and select plugin
    try:
        logger.debug("Fetching portal page: %s", actual_portal_url)
        response = session.get(actual_portal_url, timeout=10)
    except requests.exceptions.RequestException as exc:
        raise LoginError(f"Failed to reach portal: {exc}") from exc

    plugins = discover_plugins()
    plugin = select_plugin(response, plugins)

    if not plugin:
        raise LoginError("No plugin matched the captive portal")

    logger.info("Using plugin: %s", plugin.name)

    # Step 5: Execute plugin login
    success = plugin.login(session, actual_portal_url, username, password)

    if not success:
        logger.warning("Plugin '%s' login returned failure", plugin.name)
        return False

    # Step 6: Cache endpoint on success
    cache.store(CacheEntry(
        network=network,
        portal_url=actual_portal_url,
        login_endpoint=actual_portal_url,
        form_fields={},
        username_field="",
        password_field="",
    ))

    # Step 7: Verify connectivity
    return _verify_login()


def _login_via_cache(
    session: requests.Session,
    cached: CacheEntry,
    username: str,
    password: str,
) -> bool:
    """Attempt login using cached endpoint and form fields.

    Args:
        session: Requests session.
        cached: Cached portal entry.
        username: Login username.
        password: Login password.

    Returns:
        True if cached login succeeded.
    """
    payload = dict(cached.form_fields)
    if cached.username_field:
        payload[cached.username_field] = username
    if cached.password_field:
        payload[cached.password_field] = password

    try:
        response = session.post(
            cached.login_endpoint,
            data=payload,
            timeout=10,
        )
        return response.status_code == 200
    except requests.exceptions.RequestException as exc:
        logger.warning("Cached login request failed: %s", exc)
        return False


def _verify_login() -> bool:
    """Verify internet connectivity after login.

    Returns:
        True if connected to internet.
    """
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
