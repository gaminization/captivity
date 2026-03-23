"""Tests for captivity.plugins.marketplace module."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from captivity.plugins.marketplace import (
    Marketplace,
    MarketplacePlugin,
    CATALOG,
)
from captivity.plugins.registry import PluginRegistry, PluginEntry


class TestMarketplacePlugin(unittest.TestCase):
    """Test MarketplacePlugin dataclass."""

    def test_defaults(self):
        p = MarketplacePlugin(package="test", name="Test")
        self.assertEqual(p.package, "test")
        self.assertEqual(p.author, "")
        self.assertIsInstance(p.portal_types, list)

    def test_custom(self):
        p = MarketplacePlugin(
            package="captivity-plugin-cisco",
            name="Cisco",
            portal_types=["cisco"],
            author="Test Author",
        )
        self.assertEqual(p.portal_types, ["cisco"])


class TestCatalog(unittest.TestCase):
    """Test built-in catalog."""

    def test_catalog_has_plugins(self):
        self.assertGreaterEqual(len(CATALOG), 6)

    def test_cisco_in_catalog(self):
        self.assertIn("captivity-plugin-cisco", CATALOG)

    def test_all_have_names(self):
        for pkg, plugin in CATALOG.items():
            self.assertEqual(pkg, plugin.package)
            self.assertTrue(len(plugin.name) > 0)

    def test_all_have_portal_types(self):
        for plugin in CATALOG.values():
            self.assertGreater(len(plugin.portal_types), 0)


class TestMarketplace(unittest.TestCase):
    """Test Marketplace class."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = Path(self.tmpdir) / "registry.json"
        self.registry = PluginRegistry(path=self.path)
        self.mp = Marketplace(registry=self.registry)

    def test_search_all(self):
        results = self.mp.search()
        self.assertEqual(len(results), len(CATALOG))

    def test_search_cisco(self):
        results = self.mp.search("cisco")
        self.assertGreaterEqual(len(results), 1)
        self.assertTrue(any("cisco" in p.package for p in results))

    def test_search_no_results(self):
        results = self.mp.search("xyznonexistent")
        self.assertEqual(len(results), 0)

    def test_get_info(self):
        info = self.mp.get_info("captivity-plugin-cisco")
        self.assertIsNotNone(info)
        self.assertEqual(info.name, "Cisco Web Auth")

    def test_get_info_missing(self):
        self.assertIsNone(self.mp.get_info("nonexistent"))

    def test_list_installed_empty(self):
        self.assertEqual(self.mp.list_installed(), [])

    def test_install_already_installed(self):
        self.registry.register(
            PluginEntry(package="test-pkg", name="Test"),
        )
        ok, msg = self.mp.install("test-pkg")
        self.assertFalse(ok)
        self.assertIn("already installed", msg)

    @patch("captivity.plugins.marketplace.subprocess.run")
    def test_install_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        ok, msg = self.mp.install("captivity-plugin-cisco")
        self.assertTrue(ok)
        self.assertTrue(self.registry.is_installed("captivity-plugin-cisco"))

    @patch("captivity.plugins.marketplace.subprocess.run")
    def test_install_failure(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stderr="No such package",
        )
        ok, msg = self.mp.install("captivity-plugin-cisco")
        self.assertFalse(ok)
        self.assertIn("pip install failed", msg)

    def test_uninstall_not_installed(self):
        ok, msg = self.mp.uninstall("nonexistent")
        self.assertFalse(ok)
        self.assertIn("not installed", msg)

    @patch("captivity.plugins.marketplace.subprocess.run")
    def test_uninstall_success(self, mock_run):
        self.registry.register(
            PluginEntry(package="test-pkg", name="Test"),
        )
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        ok, msg = self.mp.uninstall("test-pkg")
        self.assertTrue(ok)
        self.assertFalse(self.registry.is_installed("test-pkg"))

    def test_repr(self):
        r = repr(self.mp)
        self.assertIn("installed=0", r)
        self.assertIn(f"catalog={len(CATALOG)}", r)


if __name__ == "__main__":
    unittest.main()
