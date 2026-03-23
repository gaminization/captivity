"""Tests for captivity.core.config module."""

import os
import tempfile
import unittest
from pathlib import Path

from captivity.core.config import (
    CaptivityConfig,
    ProbeConfig,
    DaemonConfig,
    DashboardConfig,
    SimulatorConfig,
    PluginsConfig,
    TelemetryConfig,
    TrayConfig,
    LoginConfig,
    load_config,
    save_config,
    generate_default_config,
    get_config,
    reset_config,
    _parse_toml,
    _to_toml,
    _coerce,
)


class TestConfigDefaults(unittest.TestCase):
    """Test default configuration values."""

    def test_probe_defaults(self):
        c = ProbeConfig()
        self.assertIn("generate_204", c.url)
        self.assertEqual(c.timeout, 5.0)

    def test_daemon_defaults(self):
        c = DaemonConfig()
        self.assertEqual(c.poll_interval, 30.0)
        self.assertEqual(c.log_level, "INFO")

    def test_dashboard_defaults(self):
        c = DashboardConfig()
        self.assertEqual(c.port, 8787)
        self.assertTrue(c.enabled)

    def test_simulator_defaults(self):
        c = SimulatorConfig()
        self.assertEqual(c.port, 9090)

    def test_login_defaults(self):
        c = LoginConfig()
        self.assertTrue(c.auto_login)
        self.assertEqual(c.max_attempts, 5)


class TestCaptivityConfig(unittest.TestCase):
    """Test main config container."""

    def setUp(self):
        self.config = CaptivityConfig()

    def test_get(self):
        val = self.config.get("probe", "url")
        self.assertIn("generate_204", val)

    def test_get_unknown_section(self):
        with self.assertRaises(KeyError):
            self.config.get("nonexistent", "key")

    def test_get_unknown_key(self):
        with self.assertRaises(KeyError):
            self.config.get("probe", "nonexistent")

    def test_set(self):
        self.config.set("probe", "timeout", 10.0)
        self.assertEqual(self.config.probe.timeout, 10.0)

    def test_set_string_coercion(self):
        self.config.set("dashboard", "port", "9999")
        self.assertEqual(self.config.dashboard.port, 9999)

    def test_set_bool_coercion(self):
        self.config.set("dashboard", "enabled", "false")
        self.assertFalse(self.config.dashboard.enabled)

    def test_sections(self):
        sections = self.config.sections()
        self.assertIn("probe", sections)
        self.assertIn("daemon", sections)
        self.assertIn("dashboard", sections)
        self.assertEqual(len(sections), 8)

    def test_keys(self):
        keys = self.config.keys("probe")
        self.assertIn("url", keys)
        self.assertIn("timeout", keys)

    def test_to_dict(self):
        d = self.config.to_dict()
        self.assertIn("probe", d)
        self.assertIn("url", d["probe"])


class TestTomlParsing(unittest.TestCase):
    """Test TOML parsing and serialization."""

    def test_parse_simple(self):
        text = '[probe]\nurl = "https://example.com"\ntimeout = 3.0\n'
        data = _parse_toml(text)
        self.assertEqual(data["probe"]["url"], "https://example.com")
        self.assertEqual(data["probe"]["timeout"], 3.0)

    def test_parse_bool(self):
        text = "[dashboard]\nenabled = true\n"
        data = _parse_toml(text)
        self.assertTrue(data["dashboard"]["enabled"])

    def test_parse_int(self):
        text = "[dashboard]\nport = 9999\n"
        data = _parse_toml(text)
        self.assertEqual(data["dashboard"]["port"], 9999)

    def test_parse_comments(self):
        text = "# comment\n[probe]\n# another\nurl = \"test\"\n"
        data = _parse_toml(text)
        self.assertEqual(data["probe"]["url"], "test")

    def test_roundtrip(self):
        config = CaptivityConfig()
        text = _to_toml(config)
        data = _parse_toml(text)
        self.assertEqual(data["dashboard"]["port"], 8787)
        self.assertIn("url", data["probe"])


class TestLoadSave(unittest.TestCase):
    """Test config file loading and saving."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = Path(self.tmpdir) / "config.toml"

    def test_load_defaults_no_file(self):
        missing = Path(self.tmpdir) / "nonexistent.toml"
        config = load_config(path=missing)
        self.assertEqual(config.dashboard.port, 8787)

    def test_save_and_load(self):
        config = CaptivityConfig()
        config.dashboard.port = 9999
        save_config(config, self.path)
        loaded = load_config(self.path)
        self.assertEqual(loaded.dashboard.port, 9999)

    def test_generate_default(self):
        path = generate_default_config(self.path)
        self.assertTrue(path.exists())
        text = path.read_text()
        self.assertIn("[probe]", text)
        self.assertIn("[daemon]", text)

    def test_file_overrides(self):
        self.path.write_text('[probe]\ntimeout = 99.0\n')
        config = load_config(self.path)
        self.assertEqual(config.probe.timeout, 99.0)
        # Non-overridden values keep defaults
        self.assertIn("generate_204", config.probe.url)


class TestEnvOverrides(unittest.TestCase):
    """Test environment variable config overrides."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = Path(self.tmpdir) / "config.toml"
        reset_config()

    def tearDown(self):
        # Clean up env vars
        for key in list(os.environ):
            if key.startswith("CAPTIVITY_"):
                del os.environ[key]
        reset_config()

    def test_env_override_string(self):
        os.environ["CAPTIVITY_PROBE_URL"] = "https://test.example.com"
        config = load_config(self.path)
        self.assertEqual(config.probe.url, "https://test.example.com")

    def test_env_override_int(self):
        os.environ["CAPTIVITY_DASHBOARD_PORT"] = "1234"
        config = load_config(self.path)
        self.assertEqual(config.dashboard.port, 1234)

    def test_env_override_bool(self):
        os.environ["CAPTIVITY_DASHBOARD_ENABLED"] = "false"
        config = load_config(self.path)
        self.assertFalse(config.dashboard.enabled)

    def test_env_overrides_file(self):
        self.path.write_text('[dashboard]\nport = 5555\n')
        os.environ["CAPTIVITY_DASHBOARD_PORT"] = "6666"
        config = load_config(self.path)
        # Env wins over file
        self.assertEqual(config.dashboard.port, 6666)


class TestSingleton(unittest.TestCase):
    """Test get_config singleton."""

    def setUp(self):
        reset_config()

    def tearDown(self):
        reset_config()

    def test_singleton(self):
        c1 = get_config()
        c2 = get_config()
        self.assertIs(c1, c2)

    def test_reset(self):
        c1 = get_config()
        reset_config()
        c2 = get_config()
        self.assertIsNot(c1, c2)


class TestCoerce(unittest.TestCase):
    """Test type coercion helper."""

    def test_bool_true(self):
        self.assertTrue(_coerce("true", bool))
        self.assertTrue(_coerce("1", bool))
        self.assertTrue(_coerce("yes", bool))

    def test_bool_false(self):
        self.assertFalse(_coerce("false", bool))
        self.assertFalse(_coerce("0", bool))

    def test_int(self):
        self.assertEqual(_coerce("42", int), 42)

    def test_float(self):
        self.assertAlmostEqual(_coerce("3.14", float), 3.14)

    def test_passthrough(self):
        self.assertEqual(_coerce(42, int), 42)


if __name__ == "__main__":
    unittest.main()
