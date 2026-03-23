"""
Network profile database for automatic network learning.

Stores learned network profiles combining:
  - Network fingerprint (gateway, portal domain, content hash)
  - Portal cache entry (login endpoint, form params)
  - Login statistics (success count, last login time)
  - Plugin preference (which plugin worked)

Profiles are persisted at: ~/.local/share/captivity/profiles.json

When connecting to a known network, the profile enables:
  1. Instant portal type recognition via fingerprint matching
  2. Direct login via cached endpoint (skip redirect detection)
  3. Correct plugin selection without probing
"""

import json
import time
from pathlib import Path
from typing import Optional

from captivity.core.fingerprint import NetworkFingerprint
from captivity.utils.logging import get_logger

logger = get_logger("profiles")

# Default profile storage following XDG spec
import os

PROFILES_DIR = Path(
    os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
) / "captivity"
PROFILES_FILE = PROFILES_DIR / "profiles.json"

# Similarity threshold for fingerprint matching
MATCH_THRESHOLD = 0.7


class NetworkProfile:
    """A learned network profile.

    Combines fingerprint data with login history to enable
    instant reconnection to known networks.

    Attributes:
        ssid: Network SSID.
        fingerprint: Network fingerprint for identification.
        plugin_name: Name of the plugin that successfully logged in.
        login_count: Number of successful logins.
        last_login: Timestamp of last successful login.
        last_seen: Timestamp of last connection to this network.
        portal_url: Last known portal URL.
        login_endpoint: Cached direct login endpoint.
        form_fields: Cached hidden form fields.
        username_field: Name of username input field.
        password_field: Name of password input field.
    """

    def __init__(
        self,
        ssid: str,
        fingerprint: Optional[NetworkFingerprint] = None,
        plugin_name: str = "",
        login_count: int = 0,
        last_login: float = 0.0,
        last_seen: float = 0.0,
        portal_url: str = "",
        login_endpoint: str = "",
        form_fields: Optional[dict] = None,
        username_field: str = "",
        password_field: str = "",
    ) -> None:
        self.ssid = ssid
        self.fingerprint = fingerprint or NetworkFingerprint(ssid=ssid)
        self.plugin_name = plugin_name
        self.login_count = login_count
        self.last_login = last_login
        self.last_seen = last_seen or time.time()
        self.portal_url = portal_url
        self.login_endpoint = login_endpoint
        self.form_fields = form_fields or {}
        self.username_field = username_field
        self.password_field = password_field

    def record_login(self, plugin_name: str = "") -> None:
        """Record a successful login."""
        self.login_count += 1
        self.last_login = time.time()
        self.last_seen = time.time()
        if plugin_name:
            self.plugin_name = plugin_name
        logger.debug("Recorded login #%d for '%s'", self.login_count, self.ssid)

    def record_seen(self) -> None:
        """Record that this network was seen (connected to)."""
        self.last_seen = time.time()

    @property
    def has_portal_info(self) -> bool:
        """Check if this profile has enough info for direct login."""
        return bool(self.login_endpoint)

    @property
    def days_since_login(self) -> float:
        """Days since last successful login."""
        if self.last_login == 0:
            return float("inf")
        return (time.time() - self.last_login) / 86400

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "ssid": self.ssid,
            "fingerprint": self.fingerprint.to_dict(),
            "plugin_name": self.plugin_name,
            "login_count": self.login_count,
            "last_login": self.last_login,
            "last_seen": self.last_seen,
            "portal_url": self.portal_url,
            "login_endpoint": self.login_endpoint,
            "form_fields": self.form_fields,
            "username_field": self.username_field,
            "password_field": self.password_field,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NetworkProfile":
        """Deserialize from dictionary."""
        fp_data = data.get("fingerprint", {})
        return cls(
            ssid=data.get("ssid", ""),
            fingerprint=NetworkFingerprint.from_dict(fp_data) if fp_data else None,
            plugin_name=data.get("plugin_name", ""),
            login_count=data.get("login_count", 0),
            last_login=data.get("last_login", 0.0),
            last_seen=data.get("last_seen", 0.0),
            portal_url=data.get("portal_url", ""),
            login_endpoint=data.get("login_endpoint", ""),
            form_fields=data.get("form_fields", {}),
            username_field=data.get("username_field", ""),
            password_field=data.get("password_field", ""),
        )

    def __repr__(self) -> str:
        return (
            f"NetworkProfile(ssid={self.ssid!r}, "
            f"plugin={self.plugin_name!r}, "
            f"logins={self.login_count})"
        )


class ProfileDatabase:
    """Persistent database of learned network profiles.

    Automatically discovers and remembers networks, enabling
    instant login on reconnection.
    """

    def __init__(self, profiles_file: Optional[Path] = None) -> None:
        self.profiles_file = profiles_file or PROFILES_FILE
        self._profiles: dict[str, NetworkProfile] = {}
        self._load()

    def _load(self) -> None:
        """Load profiles from disk."""
        if not self.profiles_file.exists():
            return

        try:
            with open(self.profiles_file, "r") as f:
                data = json.load(f)

            for key, profile_data in data.items():
                self._profiles[key] = NetworkProfile.from_dict(profile_data)

            logger.debug("Loaded %d network profiles", len(self._profiles))

        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Profiles corrupted, resetting: %s", exc)
            self._profiles = {}

    def _save(self) -> None:
        """Persist profiles to disk."""
        self.profiles_file.parent.mkdir(parents=True, exist_ok=True)

        data = {key: p.to_dict() for key, p in self._profiles.items()}

        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.debug("Saved %d network profiles", len(self._profiles))

    def get(self, ssid: str) -> Optional[NetworkProfile]:
        """Get a profile by SSID.

        Args:
            ssid: Network SSID.

        Returns:
            NetworkProfile if found, None otherwise.
        """
        return self._profiles.get(ssid)

    def find_by_fingerprint(
        self, fingerprint: NetworkFingerprint
    ) -> Optional[NetworkProfile]:
        """Find a profile matching a fingerprint.

        Uses weighted similarity scoring to find the best match
        above the threshold.

        Args:
            fingerprint: Fingerprint to match against.

        Returns:
            Best matching profile, or None if no match.
        """
        best_match = None
        best_score = 0.0

        for profile in self._profiles.values():
            score = profile.fingerprint.matches(fingerprint)
            if score > best_score and score >= MATCH_THRESHOLD:
                best_score = score
                best_match = profile

        if best_match:
            logger.info(
                "Fingerprint matched '%s' (score=%.2f)",
                best_match.ssid,
                best_score,
            )

        return best_match

    def learn(
        self,
        ssid: str,
        fingerprint: Optional[NetworkFingerprint] = None,
        plugin_name: str = "",
        portal_url: str = "",
        login_endpoint: str = "",
        form_fields: Optional[dict] = None,
        username_field: str = "",
        password_field: str = "",
    ) -> NetworkProfile:
        """Learn or update a network profile.

        Creates a new profile if the network is unknown, or updates
        the existing profile with new information.

        Args:
            ssid: Network SSID.
            fingerprint: Optional network fingerprint.
            plugin_name: Plugin that successfully logged in.
            portal_url: Portal URL.
            login_endpoint: Direct login endpoint.
            form_fields: Hidden form fields.
            username_field: Username field name.
            password_field: Password field name.

        Returns:
            The created or updated NetworkProfile.
        """
        profile = self._profiles.get(ssid)

        if profile:
            # Update existing profile
            if fingerprint and fingerprint.is_complete:
                profile.fingerprint = fingerprint
            if plugin_name:
                profile.plugin_name = plugin_name
            if portal_url:
                profile.portal_url = portal_url
            if login_endpoint:
                profile.login_endpoint = login_endpoint
            if form_fields:
                profile.form_fields = form_fields
            if username_field:
                profile.username_field = username_field
            if password_field:
                profile.password_field = password_field
            profile.record_login(plugin_name)
            logger.info("Updated profile for '%s'", ssid)
        else:
            # Create new profile
            profile = NetworkProfile(
                ssid=ssid,
                fingerprint=fingerprint or NetworkFingerprint(ssid=ssid),
                plugin_name=plugin_name,
                portal_url=portal_url,
                login_endpoint=login_endpoint,
                form_fields=form_fields or {},
                username_field=username_field,
                password_field=password_field,
            )
            profile.record_login(plugin_name)
            self._profiles[ssid] = profile
            logger.info("Learned new network '%s'", ssid)

        self._save()
        return profile

    def remove(self, ssid: str) -> bool:
        """Remove a network profile.

        Args:
            ssid: Network SSID.

        Returns:
            True if removed, False if not found.
        """
        if ssid in self._profiles:
            del self._profiles[ssid]
            self._save()
            logger.info("Removed profile for '%s'", ssid)
            return True
        return False

    def list_profiles(self) -> list[NetworkProfile]:
        """List all network profiles sorted by last seen.

        Returns:
            List of NetworkProfile objects.
        """
        return sorted(
            self._profiles.values(),
            key=lambda p: p.last_seen,
            reverse=True,
        )

    def list_ssids(self) -> list[str]:
        """List all known SSIDs.

        Returns:
            Sorted list of SSID strings.
        """
        return sorted(self._profiles.keys())

    @property
    def count(self) -> int:
        """Number of stored profiles."""
        return len(self._profiles)
