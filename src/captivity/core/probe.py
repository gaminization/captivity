"""
Connectivity probe for captive portal detection.

Uses lightweight HTTP probes to determine connectivity status:
  - HTTP 204     → Internet available (CONNECTED)
  - HTTP redirect → Captive portal detected (PORTAL_DETECTED)
  - Timeout/error → Network unavailable (NETWORK_UNAVAILABLE)
"""

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


# Lightweight probe endpoints (<1KB response)
PROBE_URL = "https://clients3.google.com/generate_204"
PROBE_TIMEOUT = 5  # seconds


def probe_connectivity(
    url: str = PROBE_URL,
    timeout: int = PROBE_TIMEOUT,
) -> tuple[ConnectivityStatus, Optional[str]]:
    """Probe internet connectivity via HTTP.

    Sends a lightweight HTTP request and interprets the response
    to determine if the device has internet access or is behind
    a captive portal.

    Args:
        url: Probe endpoint URL.
        timeout: Request timeout in seconds.

    Returns:
        Tuple of (status, redirect_url).
        redirect_url is set when a portal is detected.
    """
    try:
        response = requests.get(
            url,
            timeout=timeout,
            allow_redirects=False,
        )

        if response.status_code == 204:
            logger.debug("Probe: HTTP 204 — connected")
            return ConnectivityStatus.CONNECTED, None

        if response.status_code in (301, 302, 303, 307, 308):
            redirect_url = response.headers.get("Location", "")
            logger.info(
                "Probe: HTTP %d — portal detected (redirect: %s)",
                response.status_code,
                redirect_url,
            )
            return ConnectivityStatus.PORTAL_DETECTED, redirect_url

        # Any other response (e.g., 200 with HTML) likely indicates a portal
        logger.info(
            "Probe: HTTP %d — portal detected (non-204 response)",
            response.status_code,
        )
        return ConnectivityStatus.PORTAL_DETECTED, None

    except requests.exceptions.Timeout:
        logger.warning("Probe: timeout after %ds", timeout)
        return ConnectivityStatus.NETWORK_UNAVAILABLE, None

    except requests.exceptions.ConnectionError:
        logger.warning("Probe: connection error")
        return ConnectivityStatus.NETWORK_UNAVAILABLE, None

    except requests.exceptions.RequestException as exc:
        logger.warning("Probe: request error — %s", exc)
        return ConnectivityStatus.NETWORK_UNAVAILABLE, None
