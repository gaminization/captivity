"""
Portal endpoint cache for fast re-login.

After the first successful login, caches:
  - Portal URL
  - Login endpoint (form action)
  - Form parameters (hidden fields)

Future logins use the cached endpoint directly, bypassing
redirect detection and page parsing for reduced latency.

Cache stored at: ~/.local/share/captivity/portal_cache.json
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

from captivity.utils.logging import get_logger

logger = get_logger("cache")

# Default cache location following XDG spec
CACHE_DIR = Path(
    os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
) / "captivity"
CACHE_FILE = CACHE_DIR / "portal_cache.json"

# Cache entries expire after 7 days
CACHE_TTL = 7 * 24 * 3600


class CacheEntry:
    """A cached portal endpoint.

    Attributes:
        network: Network SSID.
        portal_url: Original portal URL.
        login_endpoint: Form action URL for direct login.
        form_fields: Hidden form fields (name → value).
        username_field: Name of the username input field.
        password_field: Name of the password input field.
        timestamp: When this entry was cached (epoch seconds).
    """

    def __init__(
        self,
        network: str,
        portal_url: str,
        login_endpoint: str,
        form_fields: dict,
        username_field: str = "",
        password_field: str = "",
        timestamp: Optional[float] = None,
    ) -> None:
        self.network = network
        self.portal_url = portal_url
        self.login_endpoint = login_endpoint
        self.form_fields = form_fields
        self.username_field = username_field
        self.password_field = password_field
        self.timestamp = timestamp or time.time()

    @property
    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return (time.time() - self.timestamp) > CACHE_TTL

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "network": self.network,
            "portal_url": self.portal_url,
            "login_endpoint": self.login_endpoint,
            "form_fields": self.form_fields,
            "username_field": self.username_field,
            "password_field": self.password_field,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CacheEntry":
        """Deserialize from dictionary."""
        return cls(
            network=data["network"],
            portal_url=data["portal_url"],
            login_endpoint=data["login_endpoint"],
            form_fields=data.get("form_fields", {}),
            username_field=data.get("username_field", ""),
            password_field=data.get("password_field", ""),
            timestamp=data.get("timestamp", 0),
        )


class PortalCache:
    """Manages cached portal endpoints.

    Stores and retrieves portal login information to enable
    fast re-login without redirect detection and page parsing.
    """

    def __init__(self, cache_file: Optional[Path] = None) -> None:
        self.cache_file = cache_file or CACHE_FILE
        self._entries: dict[str, CacheEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load cache from disk."""
        if not self.cache_file.exists():
            return

        try:
            with open(self.cache_file, "r") as f:
                data = json.load(f)

            for key, entry_data in data.items():
                entry = CacheEntry.from_dict(entry_data)
                if not entry.is_expired:
                    self._entries[key] = entry
                else:
                    logger.debug("Expired cache entry: %s", key)

            logger.debug("Loaded %d cache entries", len(self._entries))

        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Cache corrupted, resetting: %s", exc)
            self._entries = {}

    def _save(self) -> None:
        """Persist cache to disk."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

        data = {key: entry.to_dict() for key, entry in self._entries.items()}

        with open(self.cache_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.debug("Saved %d cache entries", len(self._entries))

    def get(self, network: str) -> Optional[CacheEntry]:
        """Retrieve a cached portal entry for a network.

        Args:
            network: Network SSID.

        Returns:
            CacheEntry if found and not expired, None otherwise.
        """
        entry = self._entries.get(network)

        if entry and entry.is_expired:
            logger.debug("Cache entry expired for '%s'", network)
            del self._entries[network]
            self._save()
            return None

        if entry:
            logger.debug("Cache hit for '%s'", network)

        return entry

    def store(self, entry: CacheEntry) -> None:
        """Store a portal entry in the cache.

        Args:
            entry: CacheEntry to store.
        """
        self._entries[entry.network] = entry
        self._save()
        logger.info("Cached portal endpoint for '%s'", entry.network)

    def remove(self, network: str) -> None:
        """Remove a cached entry for a network.

        Args:
            network: Network SSID.
        """
        if network in self._entries:
            del self._entries[network]
            self._save()
            logger.info("Removed cache for '%s'", network)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._entries = {}
        self._save()
        logger.info("Cache cleared")

    def list_networks(self) -> list[str]:
        """List networks with cached entries.

        Returns:
            Sorted list of network names.
        """
        return sorted(self._entries.keys())
