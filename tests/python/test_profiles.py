"""Tests for captivity.core.profiles module."""

import json
import tempfile
import unittest
from pathlib import Path

from captivity.core.fingerprint import NetworkFingerprint
from captivity.core.profiles import NetworkProfile, ProfileDatabase


class TestNetworkProfile(unittest.TestCase):
    """Test NetworkProfile class."""

    def test_create_basic(self):
        p = NetworkProfile(ssid="TestNet")
        self.assertEqual(p.ssid, "TestNet")
        self.assertEqual(p.login_count, 0)
        self.assertEqual(p.plugin_name, "")

    def test_record_login(self):
        p = NetworkProfile(ssid="TestNet")
        p.record_login("pronto")
        self.assertEqual(p.login_count, 1)
        self.assertEqual(p.plugin_name, "pronto")
        self.assertGreater(p.last_login, 0)

    def test_record_seen(self):
        p = NetworkProfile(ssid="TestNet")
        old_seen = p.last_seen
        p.record_seen()
        self.assertGreaterEqual(p.last_seen, old_seen)

    def test_has_portal_info(self):
        p = NetworkProfile(ssid="TestNet")
        self.assertFalse(p.has_portal_info)
        p.login_endpoint = "http://portal.com/login"
        self.assertTrue(p.has_portal_info)

    def test_to_dict_from_dict_roundtrip(self):
        p = NetworkProfile(
            ssid="TestNet",
            plugin_name="pronto",
            login_count=5,
            portal_url="http://portal.com",
            login_endpoint="http://portal.com/login",
            form_fields={"mode": "191"},
        )
        data = p.to_dict()
        p2 = NetworkProfile.from_dict(data)
        self.assertEqual(p.ssid, p2.ssid)
        self.assertEqual(p.plugin_name, p2.plugin_name)
        self.assertEqual(p.login_count, p2.login_count)
        self.assertEqual(p.form_fields, p2.form_fields)

    def test_repr(self):
        p = NetworkProfile(ssid="TestNet", plugin_name="generic", login_count=3)
        r = repr(p)
        self.assertIn("TestNet", r)
        self.assertIn("generic", r)
        self.assertIn("3", r)


class TestProfileDatabase(unittest.TestCase):
    """Test ProfileDatabase class."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_file = Path(self.tmpdir) / "profiles.json"
        self.db = ProfileDatabase(profiles_file=self.db_file)

    def test_empty_on_create(self):
        self.assertEqual(self.db.count, 0)

    def test_learn_new_network(self):
        fp = NetworkFingerprint(ssid="CoffeeWifi", gateway_ip="10.0.0.1")
        profile = self.db.learn(
            ssid="CoffeeWifi",
            fingerprint=fp,
            plugin_name="generic",
            portal_url="http://portal.coffee.com",
            login_endpoint="http://portal.coffee.com/login",
        )
        self.assertEqual(profile.ssid, "CoffeeWifi")
        self.assertEqual(profile.plugin_name, "generic")
        self.assertEqual(profile.login_count, 1)
        self.assertEqual(self.db.count, 1)

    def test_learn_updates_existing(self):
        self.db.learn(ssid="Net", plugin_name="generic")
        self.db.learn(ssid="Net", plugin_name="pronto", login_endpoint="/login")
        profile = self.db.get("Net")
        self.assertEqual(profile.plugin_name, "pronto")
        self.assertEqual(profile.login_count, 2)
        self.assertEqual(profile.login_endpoint, "/login")

    def test_get_existing(self):
        self.db.learn(ssid="Net")
        self.assertIsNotNone(self.db.get("Net"))

    def test_get_nonexistent(self):
        self.assertIsNone(self.db.get("Nope"))

    def test_find_by_fingerprint(self):
        fp = NetworkFingerprint(
            ssid="Net", gateway_ip="10.0.0.1",
            portal_domain="portal.com",
        )
        self.db.learn(ssid="Net", fingerprint=fp, plugin_name="pronto")

        probe_fp = NetworkFingerprint(
            ssid="Net", gateway_ip="10.0.0.1",
            portal_domain="portal.com",
        )
        match = self.db.find_by_fingerprint(probe_fp)
        self.assertIsNotNone(match)
        self.assertEqual(match.ssid, "Net")

    def test_find_no_match(self):
        fp = NetworkFingerprint(ssid="Other", gateway_ip="10.0.0.1")
        self.assertIsNone(self.db.find_by_fingerprint(fp))

    def test_remove(self):
        self.db.learn(ssid="Net")
        self.assertTrue(self.db.remove("Net"))
        self.assertIsNone(self.db.get("Net"))

    def test_remove_nonexistent(self):
        self.assertFalse(self.db.remove("Nope"))

    def test_list_profiles(self):
        self.db.learn(ssid="Net1")
        self.db.learn(ssid="Net2")
        profiles = self.db.list_profiles()
        self.assertEqual(len(profiles), 2)

    def test_list_ssids(self):
        self.db.learn(ssid="Beta")
        self.db.learn(ssid="Alpha")
        ssids = self.db.list_ssids()
        self.assertEqual(ssids, ["Alpha", "Beta"])

    def test_persistence(self):
        self.db.learn(ssid="Persistent", plugin_name="pronto")
        # Reload from disk
        db2 = ProfileDatabase(profiles_file=self.db_file)
        profile = db2.get("Persistent")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.plugin_name, "pronto")

    def test_handles_corrupt_file(self):
        with open(self.db_file, "w") as f:
            f.write("not json")
        db = ProfileDatabase(profiles_file=self.db_file)
        self.assertEqual(db.count, 0)


if __name__ == "__main__":
    unittest.main()
