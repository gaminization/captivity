"""
Connectivity probe for captive portal detection.

Multi-endpoint HTTP probe system that reliably detects captive portals:
  - Uses HTTP (not HTTPS) — portals can intercept plain HTTP
  - Probes multiple endpoints for reliable detection
  - Classifies SSL failures as portal signals
  - Inspects response HTML for captcha/login indicators
  - Returns rich ProbeResult with portal details

Detection strategy:
  1. HTTP 204/expected body → CONNECTED
  2. HTTP redirect (301/302/307/308) → PORTAL_DETECTED + redirect URL
  3. HTTP 200 with HTML (form/captcha) → PORTAL_DETECTED + content analysis
  4. SSL error on HTTPS probe → PORTAL_DETECTED (portal can't spoof certs)
  5. Connection timeout → NETWORK_UNAVAILABLE
  6. No network at all → NETWORK_UNAVAILABLE
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import requests

from captivity.utils.logging import get_logger

logger = get_logger("probe")


class ConnectivityStatus(Enum):
    """Result of a connectivity probe."""

    CONNECTED = "connected"
    PORTAL_DETECTED = "portal_detected"
    NETWORK_UNAVAILABLE = "network_unavailable"


@dataclass
class ProbeResult:
    """Rich result from a connectivity probe.

    Attributes:
        status: Overall connectivity status.
        portal_url: Redirect URL if a portal was detected via redirect.
        has_captcha: Whether the portal appears to require a CAPTCHA.
        portal_html: Snippet of the portal page HTML (first 2000 chars).
        probe_details: Per-endpoint results for debugging.
        detection_method: How the portal was detected (redirect/html/ssl/etc).
    """

    status: ConnectivityStatus
    portal_url: Optional[str] = None
    has_captcha: bool = False
    portal_html: Optional[str] = None
    probe_details: list[str] = field(default_factory=list)
    detection_method: str = ""


# --- Probe endpoints ---
# CRITICAL: Use HTTP (not HTTPS) so captive portals can intercept.
# HTTPS probes fail with SSL errors on portals, making detection harder.
PROBE_ENDPOINTS = [
    {
        "url": "http://clients3.google.com/generate_204",
        "name": "Google 204",
        "expected_status": 204,
        "expected_body": None,
    },
    {
        "url": "http://detectportal.firefox.com/success.txt",
        "name": "Firefox",
        "expected_status": 200,
        "expected_body": "success",
    },
    {
        "url": "http://www.apple.com/library/test/success.html",
        "name": "Apple",
        "expected_status": 200,
        "expected_body": "Success",
    },
]

# Fallback HTTPS probe (SSL failure = portal signal)
HTTPS_PROBE_URL = "https://clients3.google.com/generate_204"

PROBE_TIMEOUT = 5  # seconds

# Patterns that indicate captive portal HTML
PORTAL_INDICATORS = re.compile(
    r"<form|<input|captcha|login|sign.?in|terms|accept|portal|wi-?fi|password",
    re.IGNORECASE,
)

CAPTCHA_INDICATORS = re.compile(
    r"captcha|recaptcha|g-recaptcha|hcaptcha|challenge|verify.*human|"
    r"robot|automated|iframe.*captcha",
    re.IGNORECASE,
)


def _check_captcha(html: str) -> bool:
    """Check if HTML contains CAPTCHA indicators."""
    return bool(CAPTCHA_INDICATORS.search(html))


def _check_portal_html(html: str) -> bool:
    """Check if HTML looks like a captive portal page."""
    return bool(PORTAL_INDICATORS.search(html))


def _probe_single(
    url: str,
    expected_status: int,
    expected_body: Optional[str],
    timeout: int = PROBE_TIMEOUT,
) -> tuple[ConnectivityStatus, Optional[str], Optional[str]]:
    """Probe a single endpoint with strict content verification.

    Returns:
        Tuple of (status, redirect_url, response_body).
    """
    try:
        response = requests.get(
            url,
            timeout=timeout,
            allow_redirects=False,
        )

        content_type = response.headers.get("Content-Type", "")
        content_length_str = response.headers.get("Content-Length", "0")
        try:
            content_length = int(content_length_str)
        except ValueError:
            content_length = len(response.content)

        # 1. Redirects -> PORTAL
        if response.status_code in (301, 302, 303, 307, 308):
            redirect_url = response.headers.get("Location", "")
            return ConnectivityStatus.PORTAL_DETECTED, redirect_url, None

        # 2. Status code matches exactly
        if response.status_code == expected_status:
            # For 204, strict check: no body allowed
            if expected_status == 204:
                if content_length == 0 and not response.text:
                    return ConnectivityStatus.CONNECTED, None, None
                # Has unexpected body -> PORTAL spoofing 204
                return ConnectivityStatus.PORTAL_DETECTED, None, response.text[:2000]

            # For 200, check exact body match
            if expected_body and expected_body in response.text:
                return ConnectivityStatus.CONNECTED, None, None

            # Expected 200 but body didn't match -> PORTAL
            return ConnectivityStatus.PORTAL_DETECTED, None, response.text[:2000]

        # 3. Any other 200 OK with HTML content -> PORTAL
        if response.status_code == 200 and "text/html" in content_type.lower():
            return ConnectivityStatus.PORTAL_DETECTED, None, response.text[:2000]

        # 4. Fallback for anomalous responses (e.g. 403 Forbidden on Captive Portals)
        body = response.text[:2000] if response.text else None
        return ConnectivityStatus.PORTAL_DETECTED, None, body

    except requests.exceptions.SSLError:
        return ConnectivityStatus.PORTAL_DETECTED, None, None
    except requests.exceptions.RequestException:
        return ConnectivityStatus.NETWORK_UNAVAILABLE, None, None


def probe_connectivity(
    url: str = "",
    timeout: int = PROBE_TIMEOUT,
) -> tuple[ConnectivityStatus, Optional[str]]:
    """Probe internet connectivity via HTTP.

    Multi-endpoint probe with majority voting. Uses HTTP endpoints
    that captive portals can intercept (not HTTPS).

    Backward-compatible API: returns (status, redirect_url).
    Use probe_connectivity_detailed() for rich results.

    Args:
        url: Optional single probe URL override.
        timeout: Request timeout in seconds.

    Returns:
        Tuple of (status, redirect_url).
        redirect_url is set when a portal is detected.
    """
    result = probe_connectivity_detailed(url=url, timeout=timeout)
    return result.status, result.portal_url


def probe_connectivity_detailed(
    url: str = "",
    timeout: int = PROBE_TIMEOUT,
) -> ProbeResult:
    """Probe internet connectivity with detailed results.

    Multi-endpoint probe system:
      1. Tries multiple HTTP endpoints (Google 204, Firefox, Apple)
      2. Uses majority voting to determine status
      3. Falls back to HTTPS probe for SSL-based detection
      4. Inspects HTML for captcha/login indicators

    Args:
        url: Optional single probe URL override.
        timeout: Request timeout in seconds.

    Returns:
        ProbeResult with status, portal URL, captcha detection, etc.
    """
    # Single URL override (backward compat)
    if url:
        status, redirect_url, body = _probe_single(
            url,
            204,
            None,
            timeout,
        )
        result = ProbeResult(
            status=status,
            portal_url=redirect_url,
            detection_method="single_probe",
        )
        if body:
            result.portal_html = body
            result.has_captcha = _check_captcha(body)
        logger.info(
            "PROBE RESULT: %s | PORTAL DETECTED: %s | CAPTCHA DETECTED: %s",
            status.value,
            status == ConnectivityStatus.PORTAL_DETECTED,
            result.has_captcha,
        )
        return result

    # Multi-endpoint probe
    connected_count = 0
    portal_count = 0
    unavailable_count = 0
    first_redirect_url: Optional[str] = None
    first_portal_html: Optional[str] = None
    details: list[str] = []

    for endpoint in PROBE_ENDPOINTS:
        status, redirect_url, body = _probe_single(
            endpoint["url"],
            endpoint["expected_status"],
            endpoint["expected_body"],
            timeout,
        )

        detail = f"{endpoint['name']}: {status.value}"
        if redirect_url:
            detail += f" → {redirect_url}"
        details.append(detail)
        logger.debug("Probe %s: %s", endpoint["name"], detail)

        if status == ConnectivityStatus.CONNECTED:
            connected_count += 1
        elif status == ConnectivityStatus.PORTAL_DETECTED:
            portal_count += 1
            if redirect_url and not first_redirect_url:
                first_redirect_url = redirect_url
            if body and not first_portal_html:
                first_portal_html = body
        else:
            unavailable_count += 1

    # Decision logic: Multi-stage validation
    # If ANY probe detects a portal, or if probes conflict (some connected, some unavailable),
    # conservatively assume a portal is doing partial MITM.
    if portal_count > 0 or (connected_count > 0 and unavailable_count > 0):
        result = ProbeResult(
            status=ConnectivityStatus.PORTAL_DETECTED,
            portal_url=first_redirect_url,
            portal_html=first_portal_html,
            probe_details=details,
            detection_method="multi_stage_conflict"
            if portal_count == 0
            else "http_probe",
        )

        # Check for captcha in portal HTML
        if first_portal_html:
            result.has_captcha = _check_captcha(first_portal_html)
            if not first_redirect_url and _check_portal_html(first_portal_html):
                result.detection_method = "html_content"

        # If no redirect URL found, try to discover portal via HTTP request
        if not first_redirect_url:
            discovered_url = _discover_portal_url(timeout)
            if discovered_url:
                result.portal_url = discovered_url
                result.detection_method = "discovery"

    elif connected_count == len(PROBE_ENDPOINTS):
        # ONLY return connected if ALL probes succeed
        result = ProbeResult(
            status=ConnectivityStatus.CONNECTED,
            probe_details=details,
            detection_method="http_probe",
        )
    else:
        # All probes failed — try HTTPS probe to distinguish
        # portal (SSL error) vs no network (timeout)
        result = _https_fallback_probe(timeout, details)

    logger.info(
        "PROBE RESULT: %s | PORTAL DETECTED: %s | CAPTCHA DETECTED: %s | METHOD: %s",
        result.status.value,
        result.status == ConnectivityStatus.PORTAL_DETECTED,
        result.has_captcha,
        result.detection_method,
    )

    return result


def _https_fallback_probe(
    timeout: int,
    details: list[str],
) -> ProbeResult:
    """Use HTTPS probe to distinguish portal vs no network.

    If all HTTP probes failed (timeout/connection error):
      - SSL error → portal is intercepting (PORTAL_DETECTED)
      - Timeout   → genuinely no network (NETWORK_UNAVAILABLE)
      - Connection error → genuinely no network
    """
    try:
        response = requests.get(
            HTTPS_PROBE_URL,
            timeout=timeout,
            allow_redirects=False,
        )
        # If HTTPS succeeds, we're connected (HTTP failures were transient)
        if response.status_code == 204:
            details.append("HTTPS fallback: 204 (connected)")
            return ProbeResult(
                status=ConnectivityStatus.CONNECTED,
                probe_details=details,
                detection_method="https_fallback",
            )
        # Non-204 over HTTPS is unusual — treat as portal
        details.append(f"HTTPS fallback: HTTP {response.status_code} (portal?)")
        return ProbeResult(
            status=ConnectivityStatus.PORTAL_DETECTED,
            probe_details=details,
            detection_method="https_anomaly",
        )

    except requests.exceptions.SSLError:
        # SSL error = portal is intercepting → PORTAL_DETECTED
        details.append("HTTPS fallback: SSL error (portal intercepting)")
        logger.info("HTTPS SSL error — captive portal intercepting TLS")
        return ProbeResult(
            status=ConnectivityStatus.PORTAL_DETECTED,
            probe_details=details,
            detection_method="ssl_intercept",
        )

    except requests.exceptions.Timeout:
        details.append("HTTPS fallback: timeout (no network)")
        return ProbeResult(
            status=ConnectivityStatus.NETWORK_UNAVAILABLE,
            probe_details=details,
            detection_method="timeout",
        )

    except requests.exceptions.ConnectionError:
        details.append("HTTPS fallback: connection error (no network)")
        return ProbeResult(
            status=ConnectivityStatus.NETWORK_UNAVAILABLE,
            probe_details=details,
            detection_method="connection_error",
        )

    except requests.exceptions.RequestException:
        details.append("HTTPS fallback: request error")
        return ProbeResult(
            status=ConnectivityStatus.NETWORK_UNAVAILABLE,
            probe_details=details,
            detection_method="error",
        )


def _discover_portal_url(timeout: int = PROBE_TIMEOUT) -> Optional[str]:
    """Try to discover the portal URL via HTTP redirect.

    Some portals don't redirect on the 204 endpoint but do redirect
    on normal HTTP requests. Try fetching a well-known URL with
    redirects enabled.
    """
    discovery_urls = [
        "http://neverssl.com",
        "http://captive.apple.com",
        "http://example.com",
    ]

    for url in discovery_urls:
        try:
            response = requests.get(
                url,
                timeout=timeout,
                allow_redirects=True,
            )
            # If we were redirected to a different host, that's the portal
            if response.url and response.url != url:
                final_host = response.url.split("/")[2] if "/" in response.url else ""
                original_host = url.split("/")[2] if "/" in url else ""
                if final_host != original_host:
                    logger.info("Portal discovered via redirect: %s", response.url)
                    return response.url

            # If the response contains portal-like HTML
            if response.text and _check_portal_html(response.text):
                # The URL we got back IS the portal
                logger.info("Portal discovered via HTML content: %s", response.url)
                return response.url

        except requests.exceptions.RequestException:
            continue

    return None
