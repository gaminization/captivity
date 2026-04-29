"""
Captive portal login engine.

Performs the full login flow:
  1. Check portal cache for fast-path login
  2. Retrieve credentials from secure storage
  3. Probe connectivity to detect portal
  4. Select matching plugin via portal detection
  5. Execute plugin login
  6. If CAPTCHA detected → open browser for user
  7. Cache successful endpoint for future fast-path
  8. Verify connectivity

Integrates: plugins, parser, cache, credentials, probe.

CAPTCHA Handling (v2.1):
  When a portal requires CAPTCHA (e.g., T-VIT), the system:
  - Detects CAPTCHA indicators in the portal HTML
  - Opens the portal URL in the user's default browser
  - Polls connectivity until login is completed manually
  - Resumes daemon operation after successful login
"""

import os
import subprocess
from enum import Enum, auto
from typing import Optional

import requests

from captivity.core.credentials import retrieve, CredentialError
from captivity.core.probe import (
    probe_connectivity,
    probe_connectivity_detailed,
    ConnectivityStatus,
)
from captivity.core.cache import PortalCache, CacheEntry
from captivity.plugins.loader import discover_plugins, select_plugin
from captivity.utils.logging import get_logger

logger = get_logger("login")


class LoginError(Exception):
    """Raised when login fails."""


class LoginResult(Enum):
    SUCCESS = auto()
    FAILED = auto()
    WAIT_USER = auto()


def do_login(
    network: str,
    portal_url: Optional[str] = None,
    dry_run: bool = False,
    open_browser: bool = True,
) -> LoginResult:
    """Perform a captive portal login using the plugin system.

    Returns:
        LoginResult indicating the outcome.
    """
    logger.info("Starting login for network '%s'", network)

    probe_result = probe_connectivity_detailed()

    if probe_result.status == ConnectivityStatus.CONNECTED:
        logger.info("Already connected — no login needed")
        return LoginResult.SUCCESS

    if probe_result.status == ConnectivityStatus.NETWORK_UNAVAILABLE:
        logger.warning("Network unavailable — cannot login")
        return LoginResult.FAILED

    actual_portal_url = portal_url or probe_result.portal_url
    if not actual_portal_url:
        actual_portal_url = _discover_portal_via_http()

    if actual_portal_url:
        logger.info("Portal URL: %s", actual_portal_url)

    if dry_run:
        return LoginResult.SUCCESS

    if probe_result.has_captcha:
        logger.info("CAPTCHA DETECTED — requires manual user interaction")
        if open_browser:
            _handle_captcha_login(actual_portal_url)
        return LoginResult.WAIT_USER

    try:
        username, password = retrieve(network)
    except CredentialError as exc:
        logger.error("Credential retrieval failed: %s", exc)
        logger.info("Falling back to browser login")
        if open_browser:
            _handle_captcha_login(actual_portal_url)
        return LoginResult.WAIT_USER

    session = requests.Session()
    cache = PortalCache()

    cached = cache.get(network)
    if cached and not portal_url:
        success = _login_via_cache(session, cached, username, password)
        if success and _verify_login():
            return LoginResult.SUCCESS
        else:
            cache.remove(network)

    if not actual_portal_url:
        return LoginResult.FAILED

    try:
        response = session.get(actual_portal_url, timeout=10)
    except requests.exceptions.RequestException as exc:
        raise LoginError(f"Failed to reach portal: {exc}") from exc

    from captivity.core.probe import _check_captcha

    if _check_captcha(response.text):
        logger.info(
            "CAPTCHA detected in portal page — requires manual user interaction"
        )
        if open_browser:
            _handle_captcha_login(actual_portal_url)
        return LoginResult.WAIT_USER

    plugins = discover_plugins()
    plugin = select_plugin(response, plugins)

    if not plugin:
        logger.warning(
            "No plugin matched the portal — requires manual user interaction"
        )
        if open_browser:
            _handle_captcha_login(actual_portal_url)
        return LoginResult.WAIT_USER

    success = plugin.login(session, actual_portal_url, username, password)

    if not success:
        logger.warning("Automated plugin login failed. Falling back to browser.")
        if open_browser:
            _handle_captcha_login(actual_portal_url)
        return LoginResult.WAIT_USER

    cache.store(
        CacheEntry(
            network=network,
            portal_url=actual_portal_url,
            login_endpoint=actual_portal_url,
            form_fields={},
            username_field="",
            password_field="",
        )
    )

    if _verify_login():
        return LoginResult.SUCCESS

    logger.warning(
        "Login completed but connectivity not verified. Falling back to browser."
    )
    if open_browser:
        _handle_captcha_login(actual_portal_url)
    return LoginResult.WAIT_USER


def _handle_captcha_login(portal_url: Optional[str]) -> None:
    """Open the portal URL for manual user interaction."""
    if portal_url:
        logger.info("Opening portal in browser: %s", portal_url)
        _open_browser(portal_url)
    else:
        fallback_urls = [
            "http://neverssl.com",
            "http://captive.apple.com",
        ]
        for url in fallback_urls:
            logger.info("Opening fallback URL in browser: %s", url)
            _open_browser(url)
            break


def _open_browser(url: str) -> None:
    """Open a URL in the user's default browser.

    Uses xdg-open on Linux, open on macOS.
    Fails silently if no browser is available (headless server).
    """
    try:
        # Use xdg-open (Linux) or open (macOS)
        if os.name == "posix":
            cmd = "xdg-open"
            # Check if we have a display (not headless)
            display = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
            if not display:
                logger.warning(
                    "No display available — cannot open browser. "
                    "Please open manually: %s",
                    url,
                )
                return

            subprocess.Popen(
                [cmd, url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Opened browser: %s %s", cmd, url)
        else:
            logger.warning(
                "Browser auto-open not supported on %s. " "Please open manually: %s",
                os.name,
                url,
            )
    except (FileNotFoundError, OSError) as exc:
        logger.warning(
            "Failed to open browser (%s). Please open manually: %s",
            exc,
            url,
        )


def _discover_portal_via_http() -> Optional[str]:
    """Try to discover the portal URL by following HTTP redirects."""
    discovery_urls = [
        "http://neverssl.com",
        "http://captive.apple.com",
        "http://example.com",
    ]

    for url in discovery_urls:
        try:
            response = requests.get(url, timeout=5, allow_redirects=True)
            # If redirected to a different host, that's the portal
            if response.url and response.url != url:
                final_host = response.url.split("/")[2] if "/" in response.url else ""
                original_host = url.split("/")[2] if "/" in url else ""
                if final_host != original_host:
                    logger.info("Discovered portal URL: %s", response.url)
                    return response.url
        except requests.exceptions.RequestException:
            continue

    return None


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
