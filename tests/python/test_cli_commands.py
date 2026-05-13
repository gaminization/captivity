"""Tests for captivity.cli module — command handlers and parser."""

import argparse
import unittest
from unittest.mock import patch, MagicMock

from captivity.cli import (
    build_parser,
    cmd_login,
    cmd_probe,
    cmd_status,
    cmd_daemon,
    cmd_plugins,
    cmd_config,
    cmd_learn,
    cmd_stats,
    cmd_networks,
    cmd_simulate,
    cmd_daemon_rs,
    main,
)


class TestBuildParser(unittest.TestCase):
    """Test CLI argument parser construction."""

    def setUp(self):
        self.parser = build_parser()

    def test_parser_type(self):
        self.assertIsInstance(self.parser, argparse.ArgumentParser)

    def test_version_flag(self):
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["--version"])

    def test_login(self):
        args = self.parser.parse_args(["login", "-n", "X"])
        self.assertEqual(args.command, "login")

    def test_login_dry_run(self):
        args = self.parser.parse_args(["login", "-n", "X", "--dry-run"])
        self.assertTrue(args.dry_run)

    def test_probe(self):
        args = self.parser.parse_args(["probe"])
        self.assertEqual(args.command, "probe")

    def test_status(self):
        args = self.parser.parse_args(["status"])
        self.assertEqual(args.command, "status")

    def test_daemon(self):
        args = self.parser.parse_args(["daemon", "--once"])
        self.assertTrue(args.once)

    def test_plugins_search(self):
        args = self.parser.parse_args(["plugins", "search", "cisco"])
        self.assertEqual(args.plugins_action, "search")

    def test_plugins_install(self):
        args = self.parser.parse_args(["plugins", "install", "pkg"])
        self.assertEqual(args.plugins_action, "install")

    def test_plugins_uninstall(self):
        args = self.parser.parse_args(["plugins", "uninstall", "pkg"])
        self.assertEqual(args.plugins_action, "uninstall")

    def test_plugins_info(self):
        args = self.parser.parse_args(["plugins", "info", "pkg"])
        self.assertEqual(args.plugins_action, "info")

    def test_plugins_installed(self):
        args = self.parser.parse_args(["plugins", "installed"])
        self.assertEqual(args.plugins_action, "installed")

    def test_config_get(self):
        args = self.parser.parse_args(["config", "get", "probe.url"])
        self.assertEqual(args.config_action, "get")

    def test_config_set(self):
        args = self.parser.parse_args(["config", "set", "probe.url", "x"])
        self.assertEqual(args.config_action, "set")

    def test_config_init(self):
        args = self.parser.parse_args(["config", "init"])
        self.assertEqual(args.config_action, "init")

    def test_config_reset(self):
        args = self.parser.parse_args(["config", "reset"])
        self.assertEqual(args.config_action, "reset")

    def test_learn_list(self):
        args = self.parser.parse_args(["learn", "list"])
        self.assertEqual(args.learn_action, "list")

    def test_learn_show(self):
        args = self.parser.parse_args(["learn", "show", "Net"])
        self.assertEqual(args.network, "Net")

    def test_learn_forget(self):
        args = self.parser.parse_args(["learn", "forget", "Net"])
        self.assertEqual(args.learn_action, "forget")

    def test_stats_history(self):
        args = self.parser.parse_args(["stats", "history", "--limit", "5"])
        self.assertEqual(args.limit, 5)

    def test_dashboard(self):
        args = self.parser.parse_args(["dashboard", "--port", "9999"])
        self.assertEqual(args.port, 9999)

    def test_simulate_list(self):
        args = self.parser.parse_args(["simulate", "--list"])
        self.assertTrue(args.list_scenarios)

    def test_simulate_scenario(self):
        args = self.parser.parse_args(["simulate", "--scenario", "captcha"])
        self.assertEqual(args.scenario, "captcha")

    def test_daemon_rs_status(self):
        args = self.parser.parse_args(["daemon-rs", "status"])
        self.assertEqual(args.daemon_rs_action, "status")

    def test_daemon_rs_stop(self):
        args = self.parser.parse_args(["daemon-rs", "stop"])
        self.assertEqual(args.daemon_rs_action, "stop")

    def test_verbose(self):
        args = self.parser.parse_args(["-v", "probe"])
        self.assertTrue(args.verbose)

    def test_quiet(self):
        args = self.parser.parse_args(["-q", "probe"])
        self.assertTrue(args.quiet)

    def test_creds_store(self):
        args = self.parser.parse_args(["creds", "store", "Net"])
        self.assertEqual(args.creds_action, "store")

    def test_creds_list(self):
        args = self.parser.parse_args(["creds", "list"])
        self.assertEqual(args.creds_action, "list")

    def test_networks(self):
        args = self.parser.parse_args(["networks"])
        self.assertEqual(args.command, "networks")


class TestCmdLogin(unittest.TestCase):
    @patch("captivity.core.login.do_login", return_value=True)
    def test_success(self, mock_login):
        args = argparse.Namespace(network="Net", portal=None, dry_run=False)
        self.assertEqual(cmd_login(args), 0)

    @patch("captivity.core.login.do_login", return_value=False)
    def test_failure(self, mock_login):
        args = argparse.Namespace(network="Net", portal=None, dry_run=False)
        self.assertEqual(cmd_login(args), 1)

    @patch("captivity.core.login.do_login")
    def test_error(self, mock_login):
        from captivity.core.login import LoginError

        mock_login.side_effect = LoginError("fail")
        args = argparse.Namespace(network="Net", portal=None, dry_run=False)
        self.assertEqual(cmd_login(args), 1)


class TestCmdProbe(unittest.TestCase):
    @patch("captivity.core.probe.probe_connectivity_detailed")
    def test_probe(self, mock_probe):
        from captivity.core.probe import ConnectivityStatus

        result = MagicMock()
        result.status = ConnectivityStatus.CONNECTED
        result.detection_method = "http204"
        result.portal_url = None
        result.has_captcha = False
        result.probe_details = []
        mock_probe.return_value = result
        self.assertEqual(cmd_probe(argparse.Namespace()), 0)

    @patch("captivity.core.probe.probe_connectivity_detailed")
    def test_probe_with_captcha(self, mock_probe):
        from captivity.core.probe import ConnectivityStatus

        result = MagicMock()
        result.status = ConnectivityStatus.PORTAL_DETECTED
        result.detection_method = "redirect"
        result.portal_url = "http://p.com"
        result.has_captcha = True
        result.probe_details = ["detail1"]
        mock_probe.return_value = result
        self.assertEqual(cmd_probe(argparse.Namespace()), 0)


class TestCmdStatus(unittest.TestCase):
    @patch("captivity.core.probe.probe_connectivity")
    def test_connected(self, mock_probe):
        from captivity.core.probe import ConnectivityStatus

        mock_probe.return_value = (ConnectivityStatus.CONNECTED, None)
        self.assertEqual(cmd_status(argparse.Namespace()), 0)

    @patch("captivity.core.probe.probe_connectivity")
    def test_portal(self, mock_probe):
        from captivity.core.probe import ConnectivityStatus

        mock_probe.return_value = (
            ConnectivityStatus.PORTAL_DETECTED,
            "http://p",
        )
        self.assertEqual(cmd_status(argparse.Namespace()), 0)

    @patch("captivity.core.probe.probe_connectivity")
    def test_unavailable(self, mock_probe):
        from captivity.core.probe import ConnectivityStatus

        mock_probe.return_value = (ConnectivityStatus.NETWORK_UNAVAILABLE, None)
        self.assertEqual(cmd_status(argparse.Namespace()), 0)


class TestCmdDaemon(unittest.TestCase):
    @patch("captivity.daemon.runner.DaemonRunner")
    def test_once(self, mock_cls):
        runner = MagicMock()
        mock_cls.return_value = runner
        args = argparse.Namespace(network=None, portal=None, interval=30, once=True)
        self.assertEqual(cmd_daemon(args), 0)
        runner._run_probe.assert_called_once()

    @patch("captivity.daemon.runner.DaemonRunner")
    def test_run(self, mock_cls):
        runner = MagicMock()
        mock_cls.return_value = runner
        args = argparse.Namespace(network=None, portal=None, interval=30, once=False)
        self.assertEqual(cmd_daemon(args), 0)
        runner.run.assert_called_once()

    def test_daemon_cli_boots(self):
        """Regression test to ensure DaemonRunner API changes don't break CLI."""
        import subprocess
        # Run subprocess and assert it completes without crashing due to constructor errors
        result = subprocess.run(
            ["captivity", "daemon", "--network", "T-VIT", "--once"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0, f"Daemon CLI crashed: {result.stderr}")
        self.assertNotIn("unexpected keyword argument", result.stderr)


class TestCmdPlugins(unittest.TestCase):
    @patch("captivity.plugins.loader.discover_plugins")
    def test_default_list(self, mock_disc):
        p = MagicMock()
        p.name = "Test"
        p.priority = 0
        mock_disc.return_value = [p]
        args = argparse.Namespace(plugins_action=None)
        self.assertEqual(cmd_plugins(args), 0)

    @patch("captivity.plugins.loader.discover_plugins", return_value=[])
    def test_no_plugins(self, mock_disc):
        args = argparse.Namespace(plugins_action=None)
        self.assertEqual(cmd_plugins(args), 0)

    @patch("captivity.plugins.marketplace.Marketplace")
    def test_search(self, mock_mp_cls):
        mp = MagicMock()
        mp.search.return_value = []
        mock_mp_cls.return_value = mp
        args = argparse.Namespace(plugins_action="search", query="x")
        self.assertEqual(cmd_plugins(args), 0)

    @patch("captivity.plugins.marketplace.Marketplace")
    def test_search_with_results(self, mock_mp_cls):
        mp = MagicMock()
        p = MagicMock()
        p.package = "pkg"
        p.description = "desc"
        mp.search.return_value = [p]
        mp.registry.is_installed.return_value = True
        mock_mp_cls.return_value = mp
        args = argparse.Namespace(plugins_action="search", query="pkg")
        self.assertEqual(cmd_plugins(args), 0)

    @patch("captivity.plugins.marketplace.Marketplace")
    def test_install_ok(self, mock_mp_cls):
        mp = MagicMock()
        mp.install.return_value = (True, "ok")
        mock_mp_cls.return_value = mp
        args = argparse.Namespace(plugins_action="install", package="p")
        self.assertEqual(cmd_plugins(args), 0)

    @patch("captivity.plugins.marketplace.Marketplace")
    def test_install_fail(self, mock_mp_cls):
        mp = MagicMock()
        mp.install.return_value = (False, "err")
        mock_mp_cls.return_value = mp
        args = argparse.Namespace(plugins_action="install", package="p")
        self.assertEqual(cmd_plugins(args), 1)

    @patch("captivity.plugins.marketplace.Marketplace")
    def test_uninstall(self, mock_mp_cls):
        mp = MagicMock()
        mp.uninstall.return_value = (True, "ok")
        mock_mp_cls.return_value = mp
        args = argparse.Namespace(plugins_action="uninstall", package="p")
        self.assertEqual(cmd_plugins(args), 0)

    @patch("captivity.plugins.marketplace.Marketplace")
    def test_info_found(self, mock_mp_cls):
        mp = MagicMock()
        info = MagicMock()
        info.package = "p"
        info.name = "P"
        info.description = "d"
        info.version = "1.0"
        info.author = "a"
        info.portal_types = ["t"]
        info.url = "http://x"
        mp.get_info.return_value = info
        mp.registry.is_installed.return_value = False
        mock_mp_cls.return_value = mp
        args = argparse.Namespace(plugins_action="info", package="p")
        self.assertEqual(cmd_plugins(args), 0)

    @patch("captivity.plugins.marketplace.Marketplace")
    def test_info_missing(self, mock_mp_cls):
        mp = MagicMock()
        mp.get_info.return_value = None
        mock_mp_cls.return_value = mp
        args = argparse.Namespace(plugins_action="info", package="x")
        self.assertEqual(cmd_plugins(args), 1)

    @patch("captivity.plugins.loader.discover_plugins", return_value=[])
    @patch("captivity.plugins.marketplace.Marketplace")
    def test_installed_empty(self, mock_mp_cls, mock_disc):
        mp = MagicMock()
        mp.list_installed.return_value = []
        mock_mp_cls.return_value = mp
        args = argparse.Namespace(plugins_action="installed")
        self.assertEqual(cmd_plugins(args), 0)

    @patch("captivity.plugins.loader.discover_plugins", return_value=[])
    @patch("captivity.plugins.marketplace.Marketplace")
    def test_installed_with_entries(self, mock_mp_cls, mock_disc):
        mp = MagicMock()
        e = MagicMock()
        e.package = "p"
        e.version = "1.0"
        e.description = "d"
        mp.list_installed.return_value = [e]
        mock_mp_cls.return_value = mp
        args = argparse.Namespace(plugins_action="installed")
        self.assertEqual(cmd_plugins(args), 0)


class TestCmdConfig(unittest.TestCase):
    @patch("captivity.core.config.generate_default_config", return_value="/tmp/c.toml")
    def test_init(self, mock_gen):
        args = argparse.Namespace(config_action="init")
        self.assertEqual(cmd_config(args), 0)

    @patch("captivity.core.config.generate_default_config", return_value="/tmp/c.toml")
    @patch("captivity.core.config.reset_config")
    def test_reset(self, mock_reset, mock_gen):
        args = argparse.Namespace(config_action="reset")
        self.assertEqual(cmd_config(args), 0)

    @patch("captivity.core.config._to_toml", return_value="[probe]\nurl='x'")
    @patch("captivity.core.config.get_config")
    def test_show(self, mock_cfg, mock_toml):
        args = argparse.Namespace(config_action=None)
        self.assertEqual(cmd_config(args), 0)

    @patch("captivity.core.config.get_config")
    def test_get_key(self, mock_cfg):
        cfg = MagicMock()
        cfg.get.return_value = "http://test"
        mock_cfg.return_value = cfg
        args = argparse.Namespace(config_action="get", key="probe.url")
        self.assertEqual(cmd_config(args), 0)

    @patch("captivity.core.config.get_config")
    def test_get_bad_key(self, mock_cfg):
        cfg = MagicMock()
        cfg.get.side_effect = KeyError("nope")
        mock_cfg.return_value = cfg
        args = argparse.Namespace(config_action="get", key="bad.key")
        self.assertEqual(cmd_config(args), 1)

    @patch("captivity.core.config.get_config")
    def test_get_section(self, mock_cfg):
        from dataclasses import dataclass

        @dataclass
        class FakeSec:
            url: str = "x"

        cfg = MagicMock()
        cfg.probe = FakeSec()
        mock_cfg.return_value = cfg
        args = argparse.Namespace(config_action="get", key="probe")
        self.assertEqual(cmd_config(args), 0)

    @patch("captivity.core.config.get_config")
    def test_get_bad_section(self, mock_cfg):
        cfg = MagicMock(spec=[])
        mock_cfg.return_value = cfg
        args = argparse.Namespace(config_action="get", key="nosection")
        self.assertEqual(cmd_config(args), 1)

    @patch("captivity.core.config.save_config")
    @patch("captivity.core.config.get_config")
    def test_set(self, mock_cfg, mock_save):
        cfg = MagicMock()
        cfg.get.return_value = "newval"
        mock_cfg.return_value = cfg
        args = argparse.Namespace(config_action="set", key="probe.url", value="newval")
        self.assertEqual(cmd_config(args), 0)

    @patch("captivity.core.config.get_config")
    def test_set_no_dot(self, mock_cfg):
        args = argparse.Namespace(config_action="set", key="nodot", value="x")
        self.assertEqual(cmd_config(args), 1)

    @patch("captivity.core.config.save_config")
    @patch("captivity.core.config.get_config")
    def test_set_bad_key(self, mock_cfg, mock_save):
        cfg = MagicMock()
        cfg.set.side_effect = KeyError("bad")
        mock_cfg.return_value = cfg
        args = argparse.Namespace(config_action="set", key="bad.key", value="x")
        self.assertEqual(cmd_config(args), 1)


class TestCmdLearn(unittest.TestCase):
    @patch("captivity.core.profiles.ProfileDatabase")
    def test_list_empty(self, mock_db_cls):
        db = MagicMock()
        db.list_profiles.return_value = []
        mock_db_cls.return_value = db
        args = argparse.Namespace(learn_action="list")
        self.assertEqual(cmd_learn(args), 0)

    @patch("captivity.core.profiles.ProfileDatabase")
    def test_list_with_profiles(self, mock_db_cls):
        db = MagicMock()
        p = MagicMock()
        p.ssid = "Net"
        p.plugin_name = "pronto"
        p.has_portal_info = True
        p.login_count = 3
        p.days_since_login = 2.0
        p.fingerprint.gateway_ip = "192.168.1.1"
        p.fingerprint.portal_domain = "portal.com"
        db.list_profiles.return_value = [p]
        mock_db_cls.return_value = db
        args = argparse.Namespace(learn_action="list")
        self.assertEqual(cmd_learn(args), 0)

    @patch("captivity.core.profiles.ProfileDatabase")
    def test_list_default_action(self, mock_db_cls):
        db = MagicMock()
        db.list_profiles.return_value = []
        mock_db_cls.return_value = db
        args = argparse.Namespace(learn_action=None)
        self.assertEqual(cmd_learn(args), 0)

    @patch("captivity.core.profiles.ProfileDatabase")
    def test_show_found(self, mock_db_cls):
        db = MagicMock()
        p = MagicMock()
        p.ssid = "Net"
        p.plugin_name = "pronto"
        p.login_count = 1
        p.fingerprint.gateway_ip = "1.2.3.4"
        p.fingerprint.gateway_mac = "aa:bb"
        p.fingerprint.portal_domain = "p.com"
        p.login_endpoint = "http://p.com/login"
        db.get.return_value = p
        mock_db_cls.return_value = db
        args = argparse.Namespace(learn_action="show", network="Net")
        self.assertEqual(cmd_learn(args), 0)

    @patch("captivity.core.profiles.ProfileDatabase")
    def test_show_missing(self, mock_db_cls):
        db = MagicMock()
        db.get.return_value = None
        mock_db_cls.return_value = db
        args = argparse.Namespace(learn_action="show", network="X")
        self.assertEqual(cmd_learn(args), 1)

    @patch("captivity.core.profiles.ProfileDatabase")
    def test_forget_ok(self, mock_db_cls):
        db = MagicMock()
        db.remove.return_value = True
        mock_db_cls.return_value = db
        args = argparse.Namespace(learn_action="forget", network="X")
        self.assertEqual(cmd_learn(args), 0)

    @patch("captivity.core.profiles.ProfileDatabase")
    def test_forget_missing(self, mock_db_cls):
        db = MagicMock()
        db.remove.return_value = False
        mock_db_cls.return_value = db
        args = argparse.Namespace(learn_action="forget", network="X")
        self.assertEqual(cmd_learn(args), 1)


class TestCmdStats(unittest.TestCase):
    @patch("captivity.telemetry.stats.StatsDatabase")
    def test_default_empty(self, mock_db_cls):
        db = MagicMock()
        db.get_all_stats.return_value = []
        mock_db_cls.return_value = db
        args = argparse.Namespace(stats_action=None)
        self.assertEqual(cmd_stats(args), 0)

    @patch("captivity.telemetry.stats.StatsDatabase")
    def test_default_with_data(self, mock_db_cls):
        db = MagicMock()
        ns = MagicMock()
        ns.ssid = "Net"
        ns.login_successes = 5
        ns.login_failures = 1
        ns.success_rate = 0.83
        ns.total_uptime = 3600
        ns.total_rx_bytes = 1000
        ns.total_tx_bytes = 500
        ns.reconnect_count = 2
        db.get_all_stats.return_value = [ns]
        db.total_logins = 6
        db.total_uptime = 3600
        db.total_bandwidth = 1500
        mock_db_cls.return_value = db
        args = argparse.Namespace(stats_action=None)
        self.assertEqual(cmd_stats(args), 0)

    @patch("captivity.telemetry.stats.StatsDatabase")
    def test_history_empty(self, mock_db_cls):
        db = MagicMock()
        db.get_history.return_value = []
        mock_db_cls.return_value = db
        args = argparse.Namespace(stats_action="history", limit=20)
        self.assertEqual(cmd_stats(args), 0)

    @patch("captivity.telemetry.stats.StatsDatabase")
    def test_history_with_events(self, mock_db_cls):
        db = MagicMock()
        ev = MagicMock()
        ev.timestamp = 1714000000.0
        ev.event_type = "login"
        ev.network = "Net"
        ev.details = "ok"
        db.get_history.return_value = [ev]
        mock_db_cls.return_value = db
        args = argparse.Namespace(stats_action="history", limit=20)
        self.assertEqual(cmd_stats(args), 0)


class TestCmdSimulate(unittest.TestCase):
    def test_list(self):
        args = argparse.Namespace(list_scenarios=True, scenario="simple", port=9090)
        self.assertEqual(cmd_simulate(args), 0)

    def test_unknown_scenario(self):
        args = argparse.Namespace(list_scenarios=False, scenario="nonexist", port=9090)
        self.assertEqual(cmd_simulate(args), 1)


class TestCmdDaemonRs(unittest.TestCase):
    @patch("captivity.daemon.bridge.DaemonBridge")
    def test_status_connected(self, mock_cls):
        bridge = MagicMock()
        bridge.connect.return_value = True
        bridge.get_status.return_value = "connected"
        mock_cls.return_value = bridge
        args = argparse.Namespace(daemon_rs_action="status")
        self.assertEqual(cmd_daemon_rs(args), 0)

    @patch("captivity.daemon.bridge.DaemonBridge")
    def test_status_not_running(self, mock_cls):
        bridge = MagicMock()
        bridge.connect.return_value = False
        mock_cls.return_value = bridge
        args = argparse.Namespace(daemon_rs_action="status")
        self.assertEqual(cmd_daemon_rs(args), 0)

    @patch("captivity.daemon.bridge.DaemonBridge")
    def test_stop(self, mock_cls):
        bridge = MagicMock()
        bridge.connect.return_value = True
        mock_cls.return_value = bridge
        args = argparse.Namespace(daemon_rs_action="stop")
        self.assertEqual(cmd_daemon_rs(args), 0)

    @patch("captivity.daemon.bridge.DaemonBridge")
    def test_probe(self, mock_cls):
        bridge = MagicMock()
        bridge.connect.return_value = True
        bridge.get_status.return_value = "ok"
        mock_cls.return_value = bridge
        args = argparse.Namespace(daemon_rs_action="probe")
        self.assertEqual(cmd_daemon_rs(args), 0)

    @patch("captivity.daemon.bridge._find_daemon_binary", return_value=None)
    def test_start_no_binary(self, mock_find):
        args = argparse.Namespace(daemon_rs_action=None)
        self.assertEqual(cmd_daemon_rs(args), 1)

    @patch("captivity.daemon.bridge.start_daemon")
    @patch("captivity.daemon.bridge._find_daemon_binary", return_value="/usr/bin/cd")
    def test_start_fails(self, mock_find, mock_start):
        mock_start.return_value = None
        args = argparse.Namespace(daemon_rs_action=None)
        self.assertEqual(cmd_daemon_rs(args), 1)


class TestCmdNetworks(unittest.TestCase):
    @patch("captivity.core.credentials.list_networks", return_value=[])
    @patch("captivity.core.cache.PortalCache")
    def test_no_networks(self, mock_cache_cls, mock_list):
        cache = MagicMock()
        cache.list_networks.return_value = []
        mock_cache_cls.return_value = cache
        args = argparse.Namespace()
        self.assertEqual(cmd_networks(args), 0)

    @patch("captivity.core.credentials.list_networks", return_value=["Net1"])
    @patch("captivity.core.cache.PortalCache")
    def test_with_networks(self, mock_cache_cls, mock_list):
        cache = MagicMock()
        cache.list_networks.return_value = ["Net2"]
        mock_cache_cls.return_value = cache
        args = argparse.Namespace()
        self.assertEqual(cmd_networks(args), 0)


class TestMain(unittest.TestCase):
    def test_no_command(self):
        with patch("sys.argv", ["captivity"]):
            with patch("captivity.cli.sys.exit", side_effect=SystemExit(0)):
                with self.assertRaises(SystemExit):
                    main()


if __name__ == "__main__":
    unittest.main()
