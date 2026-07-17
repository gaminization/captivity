import unittest
from unittest.mock import MagicMock, patch
from captivity.cli import main, build_parser


class TestCliMocked(unittest.TestCase):
    def setUp(self):
        self.parser = build_parser()

    @patch("captivity.core.login.do_login")
    def test_login_cmd(self, mock_login):
        mock_login.return_value = True
        with patch("sys.argv", ["captivity", "login", "-n", "test"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)
            mock_login.assert_called_once()

    @patch("captivity.core.probe.probe_connectivity_detailed")
    def test_probe_cmd(self, mock_probe):
        mock_result = MagicMock()
        mock_result.status.value = "connected"
        mock_result.has_captcha = True
        mock_probe.return_value = mock_result
        with patch("sys.argv", ["captivity", "probe"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

    @patch("captivity.core.probe.probe_connectivity")
    def test_status_cmd(self, mock_status):
        from captivity.core.probe import ConnectivityStatus

        mock_status.return_value = (ConnectivityStatus.PORTAL_DETECTED, "http://portal")
        with patch("sys.argv", ["captivity", "status"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

    @patch("captivity.daemon.runner.DaemonRunner")
    def test_daemon_cmd(self, mock_runner):
        runner_instance = mock_runner.return_value
        with patch("sys.argv", ["captivity", "daemon", "--once"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)
            runner_instance._run_probe.assert_called_once()

    @patch("captivity.core.credentials.delete")
    @patch("captivity.core.credentials.retrieve")
    @patch("captivity.core.credentials.store")
    @patch("captivity.core.credentials.list_networks")
    @patch("builtins.input", return_value="user")
    @patch("getpass.getpass", return_value="pass")
    def test_creds_cmd(
        self,
        mock_getpass,
        mock_input,
        mock_list,
        mock_store,
        mock_retrieve,
        mock_delete,
    ):
        mock_list.return_value = ["net1"]
        with patch("sys.argv", ["captivity", "creds", "list"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

        with patch("sys.argv", ["captivity", "creds", "store", "test"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)
            mock_store.assert_called_once()

        mock_retrieve.return_value = ("u", "p")
        with patch("sys.argv", ["captivity", "creds", "retrieve", "test"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

        with patch("sys.argv", ["captivity", "creds", "delete", "test"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

    @patch("captivity.plugins.marketplace.Marketplace")
    @patch("captivity.plugins.loader.discover_plugins")
    def test_plugins_cmd(self, mock_discover, mock_marketplace):
        mock_discover.return_value = []
        with patch("sys.argv", ["captivity", "plugins"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

        mock_mp = mock_marketplace.return_value
        mock_mp.search.return_value = []
        with patch("sys.argv", ["captivity", "plugins", "search", "query"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

        mock_mp.install.return_value = (True, "Installed")
        with patch("sys.argv", ["captivity", "plugins", "install", "pkg"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

        mock_mp.uninstall.return_value = (True, "Uninstalled")
        with patch("sys.argv", ["captivity", "plugins", "uninstall", "pkg"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

        mock_mp.get_info.return_value = None
        with patch("sys.argv", ["captivity", "plugins", "info", "pkg"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 1)

    @patch("captivity.core.cache.PortalCache")
    def test_networks_cmd(self, mock_cache):
        with patch("sys.argv", ["captivity", "networks"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

    @patch("captivity.core.profiles.ProfileDatabase")
    def test_learn_cmd(self, mock_db):
        mock_db_inst = mock_db.return_value
        mock_db_inst.list_profiles.return_value = []
        with patch("sys.argv", ["captivity", "learn", "list"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

        mock_profile = MagicMock()
        mock_profile.ssid = "test"
        mock_profile.login_count = 1
        mock_db_inst.get.return_value = mock_profile
        with patch("sys.argv", ["captivity", "learn", "show", "test"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

        mock_db_inst.remove.return_value = True
        with patch("sys.argv", ["captivity", "learn", "forget", "test"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

    @patch("captivity.telemetry.stats.StatsDatabase")
    def test_stats_cmd(self, mock_stats):
        db_inst = mock_stats.return_value
        db_inst.total_uptime = 3600
        db_inst.total_logins = 1
        db_inst.total_bandwidth = 1000
        db_inst.get_all_stats.return_value = []
        with patch("sys.argv", ["captivity", "stats"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

    @patch("captivity.dashboard.server.DashboardServer")
    def test_dashboard_cmd(self, mock_dash):
        with patch("sys.argv", ["captivity", "dashboard"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

    @patch("captivity.testing.simulator.PortalSimulator")
    def test_simulate_cmd(self, mock_sim):
        with patch("sys.argv", ["captivity", "simulate", "--list"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

    @patch("captivity.core.config.reset_config")
    @patch("captivity.core.config.generate_default_config")
    @patch("captivity.core.config.save_config")
    @patch("captivity.core.config.get_config")
    def test_config_cmd(self, mock_get_config, mock_save, mock_gen, mock_reset):
        mock_config = MagicMock()
        mock_config.get.return_value = "val"
        mock_get_config.return_value = mock_config
        with patch("sys.argv", ["captivity", "config", "show"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

        with patch("sys.argv", ["captivity", "config", "get", "section.key"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

        with patch("sys.argv", ["captivity", "config", "set", "section.key", "val"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

        with patch("sys.argv", ["captivity", "config", "reset"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

    @patch("captivity.daemon.bridge.start_daemon")
    @patch("captivity.daemon.bridge.DaemonBridge")
    @patch("captivity.daemon.bridge._find_daemon_binary")
    def test_daemon_rs_cmd(self, mock_find, mock_bridge, mock_start):
        mock_bridge_inst = mock_bridge.return_value
        mock_bridge_inst.connect.return_value = True
        mock_bridge_inst.get_status.return_value = "connected"
        with patch("sys.argv", ["captivity", "daemon-rs", "status"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

        with patch("sys.argv", ["captivity", "daemon-rs", "stop"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

        with patch("sys.argv", ["captivity", "daemon-rs", "probe"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

        mock_proc = MagicMock()
        mock_proc.pid = 123
        mock_start.return_value = mock_proc
        with patch("sys.argv", ["captivity", "daemon-rs"]):
            with self.assertRaises(SystemExit) as e:
                main()
            self.assertEqual(e.exception.code, 0)

    @patch("captivity.ui.tray.is_gtk_available")
    def test_tray_no_gtk(self, mock_gtk):
        mock_gtk.return_value = False
        with patch("sys.argv", ["captivity", "tray"]):
            with self.assertRaises(SystemExit) as e:
                from captivity.cli import main

                main()
            self.assertEqual(e.exception.code, 1)

    @patch("captivity.ui.tray.is_gtk_available")
    @patch("captivity.ui.tray.TrayIcon")
    def test_tray_with_gtk(self, mock_tray, mock_gtk):
        mock_gtk.return_value = True
        mock_tray_inst = mock_tray.return_value
        with patch("sys.argv", ["captivity", "tray"]):
            with self.assertRaises(SystemExit) as e:
                from captivity.cli import main

                main()
            self.assertEqual(e.exception.code, 0)
            mock_tray_inst.run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
