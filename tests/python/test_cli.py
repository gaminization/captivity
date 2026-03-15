"""Tests for captivity.cli module."""

import unittest
from unittest.mock import patch

from captivity.cli import build_parser


class TestCLI(unittest.TestCase):
    """Test CLI argument parsing."""

    def setUp(self):
        """Build the parser for each test."""
        self.parser = build_parser()

    def test_version_flag(self):
        """--version exits with version info."""
        with self.assertRaises(SystemExit) as ctx:
            self.parser.parse_args(["--version"])
        self.assertEqual(ctx.exception.code, 0)

    def test_login_requires_network(self):
        """login subcommand requires --network."""
        with self.assertRaises(SystemExit) as ctx:
            self.parser.parse_args(["login"])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_login_parses_network(self):
        """login --network parses correctly."""
        args = self.parser.parse_args(["login", "--network", "mynet"])
        self.assertEqual(args.network, "mynet")
        self.assertEqual(args.command, "login")

    def test_login_parses_portal(self):
        """login --portal parses correctly."""
        args = self.parser.parse_args([
            "login", "--network", "mynet", "--portal", "http://p.com/login",
        ])
        self.assertEqual(args.portal, "http://p.com/login")

    def test_login_parses_dry_run(self):
        """login --dry-run flag is parsed."""
        args = self.parser.parse_args([
            "login", "--network", "mynet", "--dry-run",
        ])
        self.assertTrue(args.dry_run)

    def test_probe_subcommand(self):
        """probe subcommand parses."""
        args = self.parser.parse_args(["probe"])
        self.assertEqual(args.command, "probe")

    def test_status_subcommand(self):
        """status subcommand parses."""
        args = self.parser.parse_args(["status"])
        self.assertEqual(args.command, "status")

    def test_daemon_defaults(self):
        """daemon subcommand has correct defaults."""
        args = self.parser.parse_args(["daemon"])
        self.assertEqual(args.command, "daemon")
        self.assertIsNone(args.network)
        self.assertEqual(args.interval, 30)
        self.assertFalse(args.once)

    def test_daemon_with_options(self):
        """daemon subcommand parses --network, --interval, --once."""
        args = self.parser.parse_args([
            "daemon", "--network", "campus", "--interval", "10", "--once",
        ])
        self.assertEqual(args.network, "campus")
        self.assertEqual(args.interval, 10)
        self.assertTrue(args.once)

    def test_creds_store_subcommand(self):
        """creds store parses network name."""
        args = self.parser.parse_args(["creds", "store", "mynet"])
        self.assertEqual(args.command, "creds")
        self.assertEqual(args.creds_action, "store")
        self.assertEqual(args.network, "mynet")

    def test_creds_list_subcommand(self):
        """creds list parses correctly."""
        args = self.parser.parse_args(["creds", "list"])
        self.assertEqual(args.creds_action, "list")

    def test_no_command_gives_none(self):
        """No subcommand sets command to None."""
        args = self.parser.parse_args([])
        self.assertIsNone(args.command)

    def test_short_flags(self):
        """Short flags -n and -p work for login."""
        args = self.parser.parse_args([
            "login", "-n", "net", "-p", "http://portal",
        ])
        self.assertEqual(args.network, "net")
        self.assertEqual(args.portal, "http://portal")


if __name__ == "__main__":
    unittest.main()
