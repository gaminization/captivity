"""
CLI interface for Captivity.

Provides subcommands:
    captivity login    — Perform a captive portal login
    captivity probe    — Test connectivity
    captivity status   — Show connection status
    captivity daemon   — Run background reconnect loop
    captivity creds    — Manage stored credentials
    captivity plugins  — List available plugins
    captivity networks — List known networks
    captivity tray     — Launch system tray icon
    captivity learn    — Manage learned network profiles
    captivity stats    — Show connection statistics
    captivity dashboard — Launch local web dashboard
    captivity simulate — Run portal simulator for testing
    captivity config   — Manage configuration
    captivity daemon-rs — Launch Rust networking daemon
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
    from captivity.core.probe import probe_connectivity_detailed

    result = probe_connectivity_detailed()
    print(f"Status: {result.status.value}")
    print(f"Detection method: {result.detection_method}")
    if result.portal_url:
        print(f"Portal URL: {result.portal_url}")
    if result.has_captcha:
        print("⚠ CAPTCHA detected — manual login required")
    if result.probe_details:
        print("Probe details:")
        for detail in result.probe_details:
            print(f"  • {detail}")
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
    )

    if args.once:
        runner._run_probe()
    else:
        runner.run()

    return 0


def cmd_creds(args: argparse.Namespace) -> int:
    """Handle the 'creds' subcommand."""
    from captivity.core.credentials import (
        store,
        retrieve,
        delete,
        list_networks,
        CredentialError,
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
            print("Password: ********")

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
    action = getattr(args, "plugins_action", None)

    if action == "search":
        from captivity.plugins.marketplace import Marketplace

        mp = Marketplace()
        query = getattr(args, "query", "")
        results = mp.search(query)
        if not results:
            print(f"No plugins found for '{query}'.")
            return 0
        print(f"Marketplace plugins ({len(results)}):")
        for p in results:
            installed = mp.registry.is_installed(p.package)
            mark = " [installed]" if installed else ""
            print(f"  {p.package:40s} {p.description}{mark}")
        return 0

    if action == "install":
        from captivity.plugins.marketplace import Marketplace

        mp = Marketplace()
        ok, msg = mp.install(args.package)
        print(msg)
        return 0 if ok else 1

    if action == "uninstall":
        from captivity.plugins.marketplace import Marketplace

        mp = Marketplace()
        ok, msg = mp.uninstall(args.package)
        print(msg)
        return 0 if ok else 1

    if action == "info":
        from captivity.plugins.marketplace import Marketplace

        mp = Marketplace()
        info = mp.get_info(args.package)
        if not info:
            print(f"Plugin {args.package} not found in catalog.")
            return 1
        installed = mp.registry.is_installed(info.package)
        print(f"Package:     {info.package}")
        print(f"Name:        {info.name}")
        print(f"Description: {info.description}")
        print(f"Version:     {info.version}")
        print(f"Author:      {info.author}")
        print(f"Portals:     {', '.join(info.portal_types)}")
        print(f"URL:         {info.url}")
        print(f"Installed:   {'yes' if installed else 'no'}")
        return 0

    if action == "installed":
        from captivity.plugins.marketplace import Marketplace

        mp = Marketplace()
        entries = mp.list_installed()
        if not entries:
            print("No marketplace plugins installed.")
        else:
            print(f"Installed marketplace plugins ({len(entries)}):")
            for e in entries:
                print(f"  {e.package:40s} v{e.version}  {e.description}")
        print()

    # Default: list all discovered plugins (built-in + entry points)
    from captivity.plugins.loader import discover_plugins

    plugins = discover_plugins()
    if not plugins:
        print("No plugins found.")
        return 0
    print(f"Active plugins ({len(plugins)}):")
    for plugin in plugins:
        print(f"  [{plugin.priority:>4d}] {plugin.name}")
    return 0


def cmd_networks(args: argparse.Namespace) -> int:
    """Handle the 'networks' subcommand."""
    from captivity.core.cache import PortalCache
    from captivity.core.credentials import list_networks

    cached_networks = set(PortalCache().list_networks())
    cred_networks = set(list_networks())
    all_networks = sorted(cached_networks | cred_networks)

    if not all_networks:
        print("No known networks.")
        return 0

    print(f"Known networks ({len(all_networks)}):")
    for net in all_networks:
        flags = []
        if net in cred_networks:
            flags.append("creds")
        if net in cached_networks:
            flags.append("cached")
        print(f"  • {net}  [{', '.join(flags)}]")

    return 0


def cmd_tray(args: argparse.Namespace) -> int:
    """Handle the 'tray' subcommand."""
    from captivity.ui.tray import TrayIcon, is_gtk_available
    from captivity.ui.notifier import Notifier
    from captivity.daemon.events import EventBus

    if not is_gtk_available():
        print("Error: GTK3 is required for the tray icon.")
        print("Install with: sudo apt install python3-gi gir1.2-gtk-3.0")
        return 1

    event_bus = EventBus()
    notifier = Notifier(enabled=not getattr(args, "no_notify", False))

    tray = TrayIcon(
        event_bus=event_bus,
        notifier=notifier,
        network=args.network or "",
    )
    tray.run()
    return 0


def cmd_learn(args: argparse.Namespace) -> int:
    """Handle the 'learn' subcommand."""
    from captivity.core.profiles import ProfileDatabase

    db = ProfileDatabase()
    action = getattr(args, "learn_action", None)

    if action == "list" or action is None:
        profiles = db.list_profiles()
        if not profiles:
            print("No learned networks.")
            return 0
        print(f"Learned networks ({len(profiles)}):")
        for p in profiles:
            flags = []
            if p.plugin_name:
                flags.append(f"plugin={p.plugin_name}")
            if p.has_portal_info:
                flags.append("cached")
            flags.append(f"logins={p.login_count}")
            if p.days_since_login < float("inf"):
                flags.append(f"{p.days_since_login:.0f}d ago")
            print(f"  • {p.ssid}  [{', '.join(flags)}]")
            if p.fingerprint.gateway_ip:
                print(f"    gateway: {p.fingerprint.gateway_ip}")
            if p.fingerprint.portal_domain:
                print(f"    portal:  {p.fingerprint.portal_domain}")
        return 0

    elif action == "show":
        profile = db.get(args.network)
        if not profile:
            print(f"No profile for '{args.network}'.")
            return 1
        print(f"Network: {profile.ssid}")
        print(f"Plugin:  {profile.plugin_name or '(none)'}")
        print(f"Logins:  {profile.login_count}")
        fp = profile.fingerprint
        if fp.gateway_ip:
            print(f"Gateway: {fp.gateway_ip} ({fp.gateway_mac or 'MAC unknown'})")
        if fp.portal_domain:
            print(f"Portal:  {fp.portal_domain}")
        if profile.login_endpoint:
            print(f"Endpoint: {profile.login_endpoint}")
        return 0

    elif action == "forget":
        if db.remove(args.network):
            print(f"Forgot '{args.network}'.")
            return 0
        else:
            print(f"No profile for '{args.network}'.")
            return 1

    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Handle the 'stats' subcommand."""
    from captivity.telemetry.stats import StatsDatabase
    from captivity.telemetry.bandwidth import format_bytes
    import time as _time

    db = StatsDatabase()
    action = getattr(args, "stats_action", None)

    if action == "history":
        events = db.get_history(limit=getattr(args, "limit", 20))
        if not events:
            print("No connection history.")
            return 0
        print(f"Recent events ({len(events)}):")
        for e in events:
            ts = _time.strftime("%Y-%m-%d %H:%M", _time.localtime(e.timestamp))
            detail = f"  ({e.details})" if e.details else ""
            print(f"  {ts}  {e.event_type:15s}  {e.network}{detail}")
        return 0

    # Default: summary
    all_stats = db.get_all_stats()
    if not all_stats:
        print("No statistics recorded yet.")
        return 0

    print("Connection Statistics")
    print(f"  Total logins:    {db.total_logins}")
    hours = db.total_uptime / 3600
    print(f"  Total uptime:    {hours:.1f} hours")
    print(f"  Total bandwidth: {format_bytes(db.total_bandwidth)}")
    print()
    print("Per-network:")
    for ns in all_stats:
        rate = (
            f"{ns.success_rate * 100:.0f}%"
            if (ns.login_successes + ns.login_failures) > 0
            else "n/a"
        )
        print(f"  {ns.ssid}")
        print(
            f"    logins: {ns.login_successes} ok / {ns.login_failures} fail ({rate})"
        )
        print(
            f"    uptime: {ns.total_uptime / 3600:.1f}h  bw: {format_bytes(ns.total_rx_bytes + ns.total_tx_bytes)}"
        )
        if ns.reconnect_count:
            print(f"    reconnects: {ns.reconnect_count}")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Handle the 'dashboard' subcommand."""
    from captivity.dashboard.server import DashboardServer

    port = getattr(args, "port", 8787)
    host = getattr(args, "host", "127.0.0.1")
    if getattr(args, "remote", False):
        host = "0.0.0.0"
    password = getattr(args, "password", None)

    server = DashboardServer(host=host, port=port, password=password)
    auth_msg = " (password protected)" if password else ""
    print(f"Starting dashboard at http://{host}:{port}{auth_msg}")
    print("Press Ctrl+C to stop.")
    server.start(blocking=True)
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    """Handle the 'simulate' subcommand."""
    from captivity.testing.scenarios import SCENARIOS
    from captivity.testing.simulator import PortalSimulator

    if getattr(args, "list_scenarios", False):
        print("Available scenarios:")
        for name, s in sorted(SCENARIOS.items()):
            print(f"  {name:16s}  {s.description}")
        return 0

    scenario_name = getattr(args, "scenario", "simple")
    if scenario_name not in SCENARIOS:
        print(f"Unknown scenario: {scenario_name}")
        print(f"Available: {', '.join(sorted(SCENARIOS))}")
        return 1

    port = getattr(args, "port", 9090)
    scenario = SCENARIOS[scenario_name]
    sim = PortalSimulator(scenario=scenario, port=port)
    print(f"Starting portal simulator at http://127.0.0.1:{port}")
    print(f"Scenario: {scenario.name} — {scenario.description}")
    print("Press Ctrl+C to stop.")
    sim.start()
    try:
        import time as _t

        while True:
            _t.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        sim.stop()
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Handle the 'config' subcommand."""
    from captivity.core.config import (
        get_config,
        save_config,
        generate_default_config,
        _to_toml,
        reset_config,
    )

    action = getattr(args, "config_action", None)

    if action == "init":
        path = generate_default_config()
        print(f"Generated default config: {path}")
        return 0

    if action == "get":
        config = get_config()
        key_str = args.key
        if "." not in key_str:
            # Show entire section
            try:
                sec = getattr(config, key_str)
                from dataclasses import fields as dc_fields

                for f in dc_fields(sec):
                    print(f"{key_str}.{f.name} = {getattr(sec, f.name)!r}")
            except AttributeError:
                print(f"Unknown section: {key_str}")
                return 1
            return 0
        section, _, key = key_str.partition(".")
        try:
            val = config.get(section, key)
            print(f"{key_str} = {val!r}")
        except KeyError as exc:
            print(str(exc))
            return 1
        return 0

    if action == "set":
        config = get_config()
        key_str = args.key
        value = args.value
        if "." not in key_str:
            print("Key must be section.key format (e.g. probe.url)")
            return 1
        section, _, key = key_str.partition(".")
        try:
            config.set(section, key, value)
            save_config(config)
            print(f"Set {key_str} = {config.get(section, key)!r}")
        except KeyError as exc:
            print(str(exc))
            return 1
        return 0

    if action == "reset":
        reset_config()
        path = generate_default_config()
        print(f"Config reset to defaults: {path}")
        return 0

    # Default: show all
    config = get_config()
    print(_to_toml(config))
    return 0


def cmd_daemon_rs(args: argparse.Namespace) -> int:
    """Handle the 'daemon-rs' subcommand."""
    from captivity.daemon.bridge import (
        DaemonBridge,
        start_daemon,
        _find_daemon_binary,
    )

    action = getattr(args, "daemon_rs_action", None)

    if action == "status":
        bridge = DaemonBridge()
        if bridge.connect():
            status = bridge.get_status()
            print(f"Daemon status: {status}")
        else:
            print("Daemon not running")
        return 0

    if action == "stop":
        bridge = DaemonBridge()
        if bridge.connect():
            bridge.stop_daemon()
            print("Stop command sent")
        else:
            print("Daemon not running")
        return 0

    if action == "probe":
        bridge = DaemonBridge()
        if bridge.connect():
            bridge.request_probe()
            status = bridge.get_status()
            print(f"Probe result: {status}")
        else:
            print("Daemon not running")
        return 0

    # Default: start daemon
    binary = _find_daemon_binary()
    if not binary:
        print("captivity-daemon binary not found.")
        print("Build it with: cd daemon-rs && cargo build --release")
        return 1

    proc = start_daemon()
    if proc:
        print(f"Rust daemon started (PID {proc.pid})")
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            print("\nDaemon stopped")
        return 0
    else:
        print("Failed to start daemon")
        return 1


def cmd_install(args: argparse.Namespace) -> int:
    """Handle the 'install' subcommand."""
    import os
    import shutil
    import subprocess
    from pathlib import Path
    import tempfile

    print("Setting up Captivity...\n")
    
    # 1. System Dependencies (Tray)
    if shutil.which("apt-get"):
        print("1/4 Installing system dependencies (GTK3 for systray)...")
        print("    You may be prompted for your sudo password.")
        try:
            subprocess.run(["sudo", "apt-get", "update"], check=True)
            subprocess.run(["sudo", "apt-get", "install", "-y", "python3-gi", "gir1.2-gtk-3.0"], check=True)
            print("  ✓ GTK3 dependencies installed\n")
        except subprocess.CalledProcessError as exc:
            print(f"  ⚠ Failed to install GTK dependencies (ignoring): {exc}\n")
    
    # 2. Find binary path & Symlink
    print("2/5 Configuring daemon and global PATH...")
    # Use sys.argv[0] to get the exact script being executed, then resolve any existing symlinks
    binary_path = os.path.realpath(shutil.which("captivity") or sys.argv[0])
    if not os.path.exists(binary_path):
        print(f"Error: Could not determine absolute path for captivity executable ({binary_path})")
        return 1

    # Ensure captivity is globally available in PATH
    target_symlink = "/usr/local/bin/captivity"
    if binary_path != target_symlink:
        try:
            subprocess.run(["sudo", "ln", "-sf", binary_path, target_symlink], check=True)
            print(f"  ✓ Created global symlink at {target_symlink}\n")
        except subprocess.CalledProcessError as exc:
            print(f"  ⚠ Failed to create global symlink (ignoring): {exc}\n")
    else:
        print(f"  ✓ Executable is already at {target_symlink}\n")

    # 3. Generate service file
    service_content = f"""[Unit]
Description=Captivity Autonomous Login Daemon
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={binary_path} daemon
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""
    
    user_systemd_dir = Path.home() / ".config" / "systemd" / "user"
    user_systemd_dir.mkdir(parents=True, exist_ok=True)
    
    service_file = user_systemd_dir / "captivity.service"
    service_file.write_text(service_content)
    print(f"  ✓ Written service file to {service_file}")

    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", "captivity"], check=True)
        print("  ✓ User service enabled and started")
    except subprocess.CalledProcessError as exc:
        print(f"  ✗ Failed to enable systemd service: {exc}")
        return 1
        
    try:
        user = os.environ.get("USER", os.environ.get("LOGNAME", ""))
        if user:
            subprocess.run(["loginctl", "enable-linger", user], check=True, capture_output=True)
            print(f"  ✓ Linger enabled for {user}\n")
    except Exception:
        print("  ⚠ Could not enable linger — service won't auto-start at boot without an active session\n")
        
    # 4. Dispatcher script (Instant Reconnect)
    print("4/5 Installing NetworkManager dispatcher for instant reconnects...")
    dispatcher_content = """#!/bin/bash
# /etc/NetworkManager/dispatcher.d/99-captivity
# NetworkManager dispatcher script for Captivity.

INTERFACE="$1"
STATUS="$2"

logger "[captivity-dispatcher] DISPATCHER_EVENT interface=$INTERFACE status=$STATUS"

case "$STATUS" in
    up|connectivity-change|dhcp4-change|dhcp6-change)
        logger "[captivity-dispatcher] Triggering captivity restart for status=$STATUS"
        for SERVICE_FILE in /home/*/.config/systemd/user/captivity.service; do
            if [ -f "$SERVICE_FILE" ]; then
                USER_HOME=$(dirname $(dirname $(dirname $(dirname "$SERVICE_FILE"))))
                TARGET_USER=$(basename "$USER_HOME")
                TARGET_UID=$(id -u "$TARGET_USER" 2>/dev/null)
                if [ -n "$TARGET_UID" ]; then
                    logger "[captivity-dispatcher] Restarting captivity user service for $TARGET_USER"
                    sudo -u "$TARGET_USER" XDG_RUNTIME_DIR=/run/user/"$TARGET_UID" systemctl --user restart captivity || true
                fi
            fi
        done
        ;;
    *)
        ;;
esac
"""
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(dispatcher_content)
            temp_path = f.name
        
        subprocess.run(["sudo", "cp", temp_path, "/etc/NetworkManager/dispatcher.d/99-captivity"], check=True)
        subprocess.run(["sudo", "chmod", "755", "/etc/NetworkManager/dispatcher.d/99-captivity"], check=True)
        os.unlink(temp_path)
        print("  ✓ NetworkManager dispatcher installed\n")
    except subprocess.CalledProcessError as exc:
        print(f"  ✗ Failed to install NetworkManager dispatcher: {exc}\n")

    # 5. System Tray Autostart
    print("5/5 Configuring System Tray Autostart...")
    autostart_dir = Path.home() / ".config" / "autostart"
    autostart_dir.mkdir(parents=True, exist_ok=True)
    
    desktop_file = autostart_dir / "captivity-tray.desktop"
    desktop_content = f"""[Desktop Entry]
Type=Application
Name=Captivity
GenericName=WiFi Portal Login
Comment=Autonomous captive portal login
Exec={binary_path} tray
Icon=network-wireless
Terminal=false
Categories=Network;System;Monitor;
StartupNotify=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
"""
    desktop_file.write_text(desktop_content)
    print(f"  ✓ Written autostart file to {desktop_file}")
    
    # Try to launch it right now in the background
    try:
        subprocess.Popen([binary_path, "tray"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("  ✓ Launched system tray icon\n")
    except Exception as exc:
        print(f"  ⚠ Could not launch system tray immediately: {exc}\n")

    print("Setup complete! Captivity is now running in the background.")
    
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="captivity",
        description="Captivity — Autonomous captive portal login client",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"captivity {__version__}",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug output",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress output except errors",
    )

    # Global parser for common flags like --verbose
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug output"
    )
    global_parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress output except errors"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # login
    login_parser = subparsers.add_parser("login", help="Login to a captive portal", parents=[global_parser])
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
    daemon_parser = subparsers.add_parser("daemon", help="Run reconnect daemon", parents=[global_parser])
    daemon_parser.add_argument("--network", "-n", default=None, help="Network name")
    daemon_parser.add_argument("--portal", "-p", default=None, help="Portal URL")
    daemon_parser.add_argument("--once", action="store_true", help="Run a single probe")
    daemon_parser.set_defaults(func=cmd_daemon)

    # creds
    creds_parser = subparsers.add_parser("creds", help="Manage credentials")
    creds_sub = creds_parser.add_subparsers(
        dest="creds_action", help="Credential commands"
    )
    store_p = creds_sub.add_parser("store", help="Store credentials")
    store_p.add_argument("network", help="Network name")
    retrieve_p = creds_sub.add_parser("retrieve", help="Retrieve credentials")
    retrieve_p.add_argument("network", help="Network name")
    delete_p = creds_sub.add_parser("delete", help="Delete credentials")
    delete_p.add_argument("network", help="Network name")
    creds_sub.add_parser("list", help="List stored networks")
    creds_parser.set_defaults(func=cmd_creds)

    # plugins
    plugins_parser = subparsers.add_parser(
        "plugins",
        help="Manage plugins and marketplace",
    )
    plugins_sub = plugins_parser.add_subparsers(
        dest="plugins_action",
        help="Plugin commands",
    )
    search_p = plugins_sub.add_parser("search", help="Search marketplace")
    search_p.add_argument("query", nargs="?", default="", help="Search query")
    install_p = plugins_sub.add_parser("install", help="Install a plugin")
    install_p.add_argument("package", help="Plugin package name")
    uninstall_p = plugins_sub.add_parser("uninstall", help="Uninstall a plugin")
    uninstall_p.add_argument("package", help="Plugin package name")
    info_p = plugins_sub.add_parser("info", help="Show plugin details")
    info_p.add_argument("package", help="Plugin package name")
    plugins_sub.add_parser("installed", help="List installed marketplace plugins")
    plugins_parser.set_defaults(func=cmd_plugins)

    # networks
    networks_parser = subparsers.add_parser("networks", help="List known networks")
    networks_parser.set_defaults(func=cmd_networks)

    # tray
    tray_parser = subparsers.add_parser("tray", help="Launch system tray icon")
    tray_parser.add_argument("--network", "-n", default=None, help="Network name")
    tray_parser.add_argument(
        "--no-notify", action="store_true", help="Disable notifications"
    )
    tray_parser.set_defaults(func=cmd_tray)

    # learn
    learn_parser = subparsers.add_parser("learn", help="Manage learned networks")
    learn_sub = learn_parser.add_subparsers(dest="learn_action", help="Learn commands")
    learn_sub.add_parser("list", help="List learned networks")
    show_p = learn_sub.add_parser("show", help="Show network profile")
    show_p.add_argument("network", help="Network SSID")
    forget_p = learn_sub.add_parser("forget", help="Forget a network")
    forget_p.add_argument("network", help="Network SSID")
    learn_parser.set_defaults(func=cmd_learn)

    # stats
    stats_parser = subparsers.add_parser("stats", help="Show connection statistics")
    stats_sub = stats_parser.add_subparsers(dest="stats_action", help="Stats commands")
    hist_p = stats_sub.add_parser("history", help="Show event history")
    hist_p.add_argument("--limit", type=int, default=20, help="Number of events")
    stats_parser.set_defaults(func=cmd_stats)

    # dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Launch web dashboard")
    dash_parser.add_argument("--port", type=int, default=8787, help="Dashboard port")
    dash_parser.add_argument("--host", type=str, default="127.0.0.1", help="Bind host")
    dash_parser.add_argument(
        "--remote", action="store_true", help="Bind to 0.0.0.0 for remote access"
    )
    dash_parser.add_argument(
        "--password", type=str, default=None, help="Require password for access"
    )
    dash_parser.set_defaults(func=cmd_dashboard)

    # simulate
    sim_parser = subparsers.add_parser(
        "simulate",
        help="Run portal simulator for testing",
    )
    sim_parser.add_argument(
        "--port",
        type=int,
        default=9090,
        help="Simulator port (default: 9090)",
    )
    sim_parser.add_argument(
        "--scenario",
        default="simple",
        help="Scenario name (default: simple)",
    )
    sim_parser.add_argument(
        "--list",
        dest="list_scenarios",
        action="store_true",
        help="List available scenarios",
    )
    sim_parser.set_defaults(func=cmd_simulate)

    # config
    config_parser = subparsers.add_parser(
        "config",
        help="Manage configuration",
    )
    config_sub = config_parser.add_subparsers(
        dest="config_action",
        help="Config commands",
    )
    config_sub.add_parser("show", help="Show all config")
    config_sub.add_parser("init", help="Generate default config file")
    config_sub.add_parser("reset", help="Reset config to defaults")
    get_p = config_sub.add_parser("get", help="Get a config value")
    get_p.add_argument("key", help="Config key (section.key or section)")
    set_p = config_sub.add_parser("set", help="Set a config value")
    set_p.add_argument("key", help="Config key (section.key)")
    set_p.add_argument("value", help="New value")
    config_parser.set_defaults(func=cmd_config)

    # daemon-rs
    drs_parser = subparsers.add_parser(
        "daemon-rs",
        help="Launch Rust networking daemon",
    )
    drs_sub = drs_parser.add_subparsers(
        dest="daemon_rs_action",
        help="Daemon commands",
    )
    drs_sub.add_parser("status", help="Query daemon status")
    drs_sub.add_parser("stop", help="Stop the daemon")
    drs_sub.add_parser("probe", help="Request immediate probe")
    drs_parser.set_defaults(func=cmd_daemon_rs)

    # install
    install_parser = subparsers.add_parser(
        "install",
        help="Install the background systemd service",
    )
    install_parser.set_defaults(func=cmd_install)

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


if __name__ == "__main__":
    main()
