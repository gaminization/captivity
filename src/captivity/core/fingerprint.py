"""
Network fingerprinting for automatic portal identification.

Captures unique characteristics of a network to enable instant
portal recognition on reconnection:
  - Gateway IP and MAC address
  - Portal domain extracted from redirect URL
  - Redirect chain pattern (status codes)
  - Portal page content hash

Fingerprints are lightweight (<1KB each) and stored alongside
network profiles.
"""

import hashlib
import re
import subprocess
from typing import Optional

from captivity.utils.logging import get_logger

logger = get_logger("fingerprint")


class NetworkFingerprint:
    """Unique characteristics identifying a network and its portal.

    Attributes:
        ssid: Network SSID.
        gateway_ip: Default gateway IP address.
        gateway_mac: Gateway MAC address (BSSID).
        portal_domain: Domain name of the portal server.
        redirect_pattern: HTTP status codes in redirect chain.
        content_hash: SHA-256 hash of portal login page content.
    """

    def __init__(
        self,
        ssid: str,
        gateway_ip: str = "",
        gateway_mac: str = "",
        portal_domain: str = "",
        redirect_pattern: str = "",
        content_hash: str = "",
    ) -> None:
        self.ssid = ssid
        self.gateway_ip = gateway_ip
        self.gateway_mac = gateway_mac
        self.portal_domain = portal_domain
        self.redirect_pattern = redirect_pattern
        self.content_hash = content_hash

    @property
    def fingerprint_id(self) -> str:
        """Generate a unique ID from key network characteristics."""
        key = f"{self.ssid}:{self.gateway_ip}:{self.portal_domain}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    @property
    def is_complete(self) -> bool:
        """Check if fingerprint has enough data for identification."""
        return bool(self.ssid and (self.gateway_ip or self.portal_domain))

    def matches(self, other: "NetworkFingerprint") -> float:
        """Calculate a similarity score against another fingerprint.

        Returns:
            Float between 0.0 (no match) and 1.0 (exact match).
        """
        score = 0.0
        weights = 0.0

        # SSID must match
        if self.ssid != other.ssid:
            return 0.0

        score += 1.0
        weights += 1.0

        # Gateway IP match (strong signal)
        if self.gateway_ip and other.gateway_ip:
            weights += 2.0
            if self.gateway_ip == other.gateway_ip:
                score += 2.0

        # Gateway MAC match (strongest signal)
        if self.gateway_mac and other.gateway_mac:
            weights += 3.0
            if self.gateway_mac.lower() == other.gateway_mac.lower():
                score += 3.0

        # Portal domain match
        if self.portal_domain and other.portal_domain:
            weights += 2.0
            if self.portal_domain == other.portal_domain:
                score += 2.0

        # Content hash match
        if self.content_hash and other.content_hash:
            weights += 1.0
            if self.content_hash == other.content_hash:
                score += 1.0

        return score / weights if weights > 0 else 0.0

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "ssid": self.ssid,
            "gateway_ip": self.gateway_ip,
            "gateway_mac": self.gateway_mac,
            "portal_domain": self.portal_domain,
            "redirect_pattern": self.redirect_pattern,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NetworkFingerprint":
        """Deserialize from dictionary."""
        return cls(
            ssid=data.get("ssid", ""),
            gateway_ip=data.get("gateway_ip", ""),
            gateway_mac=data.get("gateway_mac", ""),
            portal_domain=data.get("portal_domain", ""),
            redirect_pattern=data.get("redirect_pattern", ""),
            content_hash=data.get("content_hash", ""),
        )

    def __repr__(self) -> str:
        parts = [f"ssid={self.ssid!r}"]
        if self.gateway_ip:
            parts.append(f"gw={self.gateway_ip}")
        if self.portal_domain:
            parts.append(f"portal={self.portal_domain}")
        return f"NetworkFingerprint({', '.join(parts)})"


def get_default_gateway() -> Optional[str]:
    """Get the default gateway IP address.

    Returns:
        Gateway IP string, or None if unavailable.
    """
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        match = re.search(r"default via (\S+)", result.stdout)
        if match:
            return match.group(1)
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("Failed to get default gateway: %s", exc)
    return None


def get_gateway_mac(gateway_ip: str) -> Optional[str]:
    """Get the MAC address of the gateway via ARP table.

    Args:
        gateway_ip: Gateway IP to look up.

    Returns:
        MAC address string, or None if unavailable.
    """
    try:
        result = subprocess.run(
            ["ip", "neigh", "show", gateway_ip],
            capture_output=True,
            text=True,
            timeout=5,
        )
        match = re.search(r"lladdr\s+(\S+)", result.stdout)
        if match:
            return match.group(1)
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("Failed to get gateway MAC: %s", exc)
    return None


def extract_portal_domain(redirect_url: str) -> str:
    """Extract the domain from a portal redirect URL.

    Args:
        redirect_url: The URL the portal redirected to.

    Returns:
        Domain string, or empty string if extraction fails.
    """
    match = re.search(r"https?://([^/]+)", redirect_url)
    return match.group(1) if match else ""


def hash_content(content: str) -> str:
    """Generate a content hash for portal fingerprinting.

    Args:
        content: HTML content of the portal page.

    Returns:
        SHA-256 hash prefix (first 32 chars).
    """
    return hashlib.sha256(content.encode()).hexdigest()[:32]


def capture_fingerprint(
    ssid: str,
    portal_url: str = "",
    portal_content: str = "",
) -> NetworkFingerprint:
    """Capture a complete network fingerprint.

    Gathers gateway info, portal domain, and content hash
    to create a reusable network fingerprint.

    Args:
        ssid: Network SSID.
        portal_url: Optional portal redirect URL.
        portal_content: Optional portal page HTML content.

    Returns:
        Populated NetworkFingerprint.
    """
    gateway_ip = get_default_gateway() or ""
    gateway_mac = ""
    if gateway_ip:
        gateway_mac = get_gateway_mac(gateway_ip) or ""

    portal_domain = extract_portal_domain(portal_url) if portal_url else ""
    content_hash = hash_content(portal_content) if portal_content else ""

    fp = NetworkFingerprint(
        ssid=ssid,
        gateway_ip=gateway_ip,
        gateway_mac=gateway_mac,
        portal_domain=portal_domain,
        content_hash=content_hash,
    )

    logger.info("Captured fingerprint: %s", fp)
    return fp
