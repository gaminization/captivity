"""Tests for captivity.plugins.registry module."""

import json
import tempfile
import unittest
from pathlib import Path

from captivity.plugins.registry import PluginRegistry, PluginEntry


class TestPluginEntry(unittest.TestCase):
    """Test PluginEntry dataclass."""

    def test_defaults(self):
        e = PluginEntry(package="test-pkg", name="Test")
        self.assertEqual(e.package, "test-pkg")
        self.assertEqual(e.name, "Test")
        self.assertEqual(e.version, "0.0.0")
        self.assertEqual(e.source, "pypi")
        self.assertIsInstance(e.portal_types, list)

    def test_custom_fields(self):
        e = PluginEntry(
            package="captivity-plugin-cisco",
            name="Cisco",
            version="1.0.0",
            description="Cisco plugin",
            source="local",
            portal_types=["cisco"],
        )
        self.assertEqual(e.version, "1.0.0")
        self.assertEqual(e.portal_types, ["cisco"])


class TestPluginRegistry(unittest.TestCase):
    """Test PluginRegistry."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = Path(self.tmpdir) / "registry.json"
        self.registry = PluginRegistry(path=self.path)

    def test_empty_registry(self):
        self.assertEqual(self.registry.count, 0)
        self.assertEqual(self.registry.list_plugins(), [])

    def test_register(self):
        entry = PluginEntry(package="test-pkg", name="Test Plugin")
        self.registry.register(entry)
        self.assertEqual(self.registry.count, 1)
        self.assertTrue(self.registry.is_installed("test-pkg"))

    def test_unregister(self):
        entry = PluginEntry(package="test-pkg", name="Test Plugin")
        self.registry.register(entry)
        result = self.registry.unregister("test-pkg")
        self.assertTrue(result)
        self.assertEqual(self.registry.count, 0)
        self.assertFalse(self.registry.is_installed("test-pkg"))

    def test_unregister_missing(self):
        result = self.registry.unregister("nonexistent")
        self.assertFalse(result)

    def test_get(self):
        entry = PluginEntry(package="test-pkg", name="Test")
        self.registry.register(entry)
        retrieved = self.registry.get("test-pkg")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "Test")

    def test_get_missing(self):
        self.assertIsNone(self.registry.get("nonexistent"))

    def test_persistence(self):
        entry = PluginEntry(package="test-pkg", name="Test", version="1.0")
        self.registry.register(entry)
        # Load new instance from same path
        registry2 = PluginRegistry(path=self.path)
        self.assertEqual(registry2.count, 1)
        self.assertEqual(registry2.get("test-pkg").version, "1.0")

    def test_corrupt_file(self):
        self.path.write_text("invalid json{{{")
        registry = PluginRegistry(path=self.path)
        self.assertEqual(registry.count, 0)

    def test_list_plugins(self):
        self.registry.register(PluginEntry(package="a", name="A"))
        self.registry.register(PluginEntry(package="b", name="B"))
        self.assertEqual(len(self.registry.list_plugins()), 2)

    def test_repr(self):
        self.assertIn("count=0", repr(self.registry))


if __name__ == "__main__":
    unittest.main()
