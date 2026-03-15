"""Tests for captivity.core.cache module."""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from captivity.core.cache import CacheEntry, PortalCache, CACHE_TTL


class TestCacheEntry(unittest.TestCase):
    """Test CacheEntry."""

    def test_not_expired(self):
        entry = CacheEntry(
            network="test",
            portal_url="http://portal",
            login_endpoint="http://portal/login",
            form_fields={"token": "abc"},
            timestamp=time.time(),
        )
        self.assertFalse(entry.is_expired)

    def test_expired(self):
        entry = CacheEntry(
            network="test",
            portal_url="http://portal",
            login_endpoint="http://portal/login",
            form_fields={},
            timestamp=time.time() - CACHE_TTL - 1,
        )
        self.assertTrue(entry.is_expired)

    def test_serialization(self):
        entry = CacheEntry(
            network="wifi",
            portal_url="http://p.com",
            login_endpoint="http://p.com/auth",
            form_fields={"k": "v"},
            username_field="user",
            password_field="pass",
        )
        data = entry.to_dict()
        restored = CacheEntry.from_dict(data)
        self.assertEqual(restored.network, "wifi")
        self.assertEqual(restored.login_endpoint, "http://p.com/auth")
        self.assertEqual(restored.form_fields, {"k": "v"})
        self.assertEqual(restored.username_field, "user")


class TestPortalCache(unittest.TestCase):
    """Test PortalCache."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cache_file = Path(self.tmpdir) / "test_cache.json"

    def tearDown(self):
        if self.cache_file.exists():
            os.remove(self.cache_file)
        os.rmdir(self.tmpdir)

    def _make_cache(self):
        return PortalCache(cache_file=self.cache_file)

    def _make_entry(self, network="test_net"):
        return CacheEntry(
            network=network,
            portal_url="http://portal.com",
            login_endpoint="http://portal.com/login",
            form_fields={"token": "abc"},
            username_field="userId",
            password_field="password",
        )

    def test_store_and_retrieve(self):
        cache = self._make_cache()
        entry = self._make_entry()
        cache.store(entry)

        result = cache.get("test_net")
        self.assertIsNotNone(result)
        self.assertEqual(result.login_endpoint, "http://portal.com/login")

    def test_persistence(self):
        """Cached data persists across instances."""
        cache1 = self._make_cache()
        cache1.store(self._make_entry())

        cache2 = self._make_cache()
        result = cache2.get("test_net")
        self.assertIsNotNone(result)

    def test_get_returns_none_for_missing(self):
        cache = self._make_cache()
        self.assertIsNone(cache.get("nonexistent"))

    def test_remove(self):
        cache = self._make_cache()
        cache.store(self._make_entry())
        cache.remove("test_net")
        self.assertIsNone(cache.get("test_net"))

    def test_clear(self):
        cache = self._make_cache()
        cache.store(self._make_entry("net1"))
        cache.store(self._make_entry("net2"))
        cache.clear()
        self.assertEqual(cache.list_networks(), [])

    def test_list_networks(self):
        cache = self._make_cache()
        cache.store(self._make_entry("alpha"))
        cache.store(self._make_entry("beta"))
        self.assertEqual(cache.list_networks(), ["alpha", "beta"])

    def test_expired_entries_pruned_on_load(self):
        """Expired entries are pruned when loading from disk."""
        data = {
            "old_net": CacheEntry(
                network="old_net",
                portal_url="http://old",
                login_endpoint="http://old/login",
                form_fields={},
                timestamp=time.time() - CACHE_TTL - 1,
            ).to_dict()
        }
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, "w") as f:
            json.dump(data, f)

        cache = self._make_cache()
        self.assertIsNone(cache.get("old_net"))


if __name__ == "__main__":
    unittest.main()
