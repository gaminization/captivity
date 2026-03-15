"""
CLI interface for Captivity.

Provides subcommands:
    captivity login    — Perform a captive portal login
    captivity probe    — Test connectivity
    captivity status   — Show connection status
    captivity daemon   — Run background reconnect loop
    captivity creds    — Manage stored credentials
    captivity plugins  — List available plugins
"""

import argparse
import sys

from captivity import __version__
from captivity.utils.logging import setup_logging, get_logger


def cmd_login(args: argparse.Namespace) -> int:
    """Handle the 'login' subcommand."""
    from captivity.core.login import do_login, LoginError
    from captivity.core.credentials import CredentialError

    try:
        success = do_login(
            network=args.network,
            portal_url=args.portal,
            dry_run=args.dry_run,
        )
        return 0 if success else 1
    except (LoginError, CredentialError) as exc:
        logger = get_logger("cli")
        logger.error("%s", exc)
        return 1


def cmd_probe(args: argparse.Namespace) -> int:
    """Handle the 'probe' subcommand."""
    from captivity.core.probe import probe_connectivity

    status, redirect_url = probe_connectivity()
    print(f"Status: {status.value}")
    if redirect_url:
        print(f"Redirect: {redirect_url}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Handle the 'status' subcommand."""
    from captivity.core.probe import probe_connectivity, ConnectivityStatus

    status, redirect_url = probe_connectivity()

    icons = {
        ConnectivityStatus.CONNECTED: "✓",
        ConnectivityStatus.PORTAL_DETECTED: "⚠",
        ConnectivityStatus.NETWORK_UNAVAILABLE: "✗",
    }
    descriptions = {
        ConnectivityStatus.CONNECTED: "Internet available",
        ConnectivityStatus.PORTAL_DETECTED: "Captive portal detected",
        ConnectivityStatus.NETWORK_UNAVAILABLE: "Network unavailable",
    }

    icon = icons.get(status, "?")
    desc = descriptions.get(status, "Unknown")
    print(f"  {icon} {desc}")

    if redirect_url:
        print(f"  Portal: {redirect_url}")

    print(f"  Version: {__version__}")
    return 0


def cmd_daemon(args: argparse.Namespace) -> int:
    """Handle the 'daemon' subcommand."""
    from captivity.daemon.runner import DaemonRunner

    runner = DaemonRunner(
        network=args.network,
        portal_url=args.portal,
        interval=args.interval,
    )

    if args.once:
        runner.run_once()
    else:
        runner.run()

    return 0


def cmd_creds(args: argparse.Namespace) -> int:
    """Handle the 'creds' subcommand."""
    from captivity.core.credentials import (
        store, retrieve, delete, list_networks, CredentialError,
    )
    import getpass

    try:
        if args.creds_action == "store":
            username = input("Username: ")
            password = getpass.getpass("Password: ")
            store(args.network, username, password)
            print(f"Credentials stored for '{args.network}'")

        elif args.creds_action == "retrieve":
            username, password = retrieve(args.network)
            print(f"Username: {username}")
            print(f"Password: {'*' * len(password)}")

        elif args.creds_action == "delete":
            delete(args.network)
            print(f"Credentials deleted for '{args.network}'")

        elif args.creds_action == "list":
            networks = list_networks()
            if networks:
                print("Stored networks:")
                for n in networks:
                    print(f"  • {n}")
            else:
                print("No stored credentials found.")

    except CredentialError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


def cmd_plugins(args: argparse.Namespace) -> int:
    """Handle the 'plugins' subcommand."""
    from captivity.plugins.loader import discover_plugins

    plugins = discover_plugins()

    if not plugins:
        print("No plugins found.")
        return 0

    print(f"Available plugins ({len(plugins)}):")
    for plugin in plugins:
        print(f"  [{plugin.priority:>4d}] {plugin.name}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="captivity",
        description="Captivity — Autonomous captive portal login client",
    )
    parser.add_argument(
        "--version", action="version", version=f"captivity {__version__}",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug output",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="Suppress output except errors",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # login
    login_parser = subparsers.add_parser("login", help="Login to a captive portal")
    login_parser.add_argument("--network", "-n", required=True, help="Network name")
    login_parser.add_argument("--portal", "-p", default=None, help="Portal URL")
    login_parser.add_argument("--dry-run", action="store_true", help="Simulate login")
    login_parser.set_defaults(func=cmd_login)

    # probe
    probe_parser = subparsers.add_parser("probe", help="Test connectivity")
    probe_parser.set_defaults(func=cmd_probe)

    # status
    status_parser = subparsers.add_parser("status", help="Show connection status")
    status_parser.set_defaults(func=cmd_status)

    # daemon
    daemon_parser = subparsers.add_parser("daemon", help="Run reconnect daemon")
    daemon_parser.add_argument("--network", "-n", default=None, help="Network name")
    daemon_parser.add_argument("--portal", "-p", default=None, help="Portal URL")
    daemon_parser.add_argument("--interval", "-i", type=int, default=30, help="Probe interval (seconds)")
    daemon_parser.add_argument("--once", action="store_true", help="Run a single probe")
    daemon_parser.set_defaults(func=cmd_daemon)

    # creds
    creds_parser = subparsers.add_parser("creds", help="Manage credentials")
    creds_sub = creds_parser.add_subparsers(dest="creds_action", help="Credential commands")
    store_p = creds_sub.add_parser("store", help="Store credentials")
    store_p.add_argument("network", help="Network name")
    retrieve_p = creds_sub.add_parser("retrieve", help="Retrieve credentials")
    retrieve_p.add_argument("network", help="Network name")
    delete_p = creds_sub.add_parser("delete", help="Delete credentials")
    delete_p.add_argument("network", help="Network name")
    creds_sub.add_parser("list", help="List stored networks")
    creds_parser.set_defaults(func=cmd_creds)

    # plugins
    plugins_parser = subparsers.add_parser("plugins", help="List available plugins")
    plugins_parser.set_defaults(func=cmd_plugins)

    return parser


def main() -> None:
    """Main entry point for the captivity CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Setup logging
    level = "DEBUG" if getattr(args, "verbose", False) else "INFO"
    quiet = getattr(args, "quiet", False)
    setup_logging(level=level, quiet=quiet)

    # Dispatch to subcommand
    exit_code = args.func(args)
    sys.exit(exit_code)
