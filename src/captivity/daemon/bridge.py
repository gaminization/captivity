"""
Bridge between Python components and the Rust daemon.

Communicates with the Rust `captivity-daemon` binary via
Unix domain socket IPC using JSON messages.

Provides:
    - DaemonBridge: client for sending commands and receiving events
    - bridges Rust events to Python EventBus

Protocol (newline-delimited JSON):
    Client → Daemon: {"command": "status"}
    Daemon → Client: {"ok": true, "status": "connected"}
"""

import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Optional, Callable

from captivity.daemon.events import Event, EventBus
from captivity.utils.logging import get_logger

logger = get_logger("bridge")


def _default_socket_path() -> str:
    """Get default socket path matching Rust daemon."""
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    return os.path.join(runtime, "captivity-daemon.sock")


def _find_daemon_binary() -> Optional[str]:
    """Locate the captivity-daemon binary."""
    # Check common locations
    candidates = [
        # In project tree (development)
        os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "daemon-rs", "target", "release",
            "captivity-daemon",
        ),
        os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "daemon-rs", "target", "debug",
            "captivity-daemon",
        ),
        # System install
        "/usr/local/bin/captivity-daemon",
        "/usr/bin/captivity-daemon",
    ]

    for path in candidates:
        resolved = os.path.realpath(path)
        if os.path.isfile(resolved) and os.access(resolved, os.X_OK):
            return resolved

    return None


class DaemonBridge:
    """Client bridge to the Rust captivity-daemon.

    Sends commands via Unix socket IPC and optionally
    subscribes to real-time events, forwarding them to
    the Python EventBus.

    Usage:
        bridge = DaemonBridge()
        if bridge.connect():
            status = bridge.get_status()
            bridge.subscribe_events(event_bus)
    """

    def __init__(self, socket_path: Optional[str] = None) -> None:
        self._socket_path = socket_path or _default_socket_path()
        self._connected = False
        self._event_thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def socket_path(self) -> str:
        """Get the IPC socket path."""
        return self._socket_path

    @property
    def is_connected(self) -> bool:
        """Check if daemon is reachable."""
        return self._connected

    def connect(self) -> bool:
        """Test connection to the daemon.

        Returns:
            True if daemon is reachable.
        """
        try:
            result = self._send_command({"command": "status"})
            self._connected = result is not None and result.get("ok", False)
            return self._connected
        except Exception as exc:
            logger.debug("Cannot connect to daemon: %s", exc)
            self._connected = False
            return False

    def get_status(self) -> Optional[str]:
        """Get current connectivity status from daemon.

        Returns:
            Status string ('connected', 'portal_detected',
            'network_unavailable') or None on error.
        """
        result = self._send_command({"command": "status"})
        if result and result.get("ok"):
            return result.get("status")
        return None

    def request_probe(self) -> bool:
        """Request an immediate connectivity probe.

        Returns:
            True if command was accepted.
        """
        result = self._send_command({"command": "probe"})
        return result is not None and result.get("ok", False)

    def stop_daemon(self) -> bool:
        """Request daemon to stop.

        Returns:
            True if command was accepted.
        """
        result = self._send_command({"command": "stop"})
        return result is not None and result.get("ok", False)

    def subscribe_events(self, event_bus: EventBus) -> None:
        """Subscribe to daemon events and forward to EventBus.

        Starts a background thread that receives events from
        the Rust daemon and publishes them on the Python EventBus.

        Args:
            event_bus: Python event bus to publish events on.
        """
        if self._event_thread and self._event_thread.is_alive():
            return

        self._running = True
        self._event_thread = threading.Thread(
            target=self._event_loop,
            args=(event_bus,),
            daemon=True,
            name="daemon-bridge-events",
        )
        self._event_thread.start()

    def unsubscribe(self) -> None:
        """Stop the event subscription thread."""
        self._running = False
        if self._event_thread:
            self._event_thread.join(timeout=2.0)

    def _send_command(self, command: dict) -> Optional[dict]:
        """Send a command to the daemon and receive response.

        Args:
            command: JSON-serializable command dict.

        Returns:
            Parsed response dict, or None on error.
        """
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect(self._socket_path)

            # Send command (newline-delimited JSON)
            msg = json.dumps(command) + "\n"
            sock.sendall(msg.encode())

            # Read response
            data = b""
            while b"\n" not in data:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk

            sock.close()

            if data:
                return json.loads(data.decode().strip())
            return None

        except (socket.error, json.JSONDecodeError, OSError) as exc:
            logger.debug("IPC error: %s", exc)
            return None

    def _event_loop(self, event_bus: EventBus) -> None:
        """Background loop receiving events from daemon."""
        # Event name mapping: Rust → Python
        event_map = {
            "NetworkConnected": Event.NETWORK_CONNECTED,
            "PortalDetected": Event.PORTAL_DETECTED,
            "SessionExpired": Event.SESSION_EXPIRED,
            "NetworkUnavailable": Event.SESSION_EXPIRED,
        }

        while self._running:
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect(self._socket_path)

                # Subscribe to events
                msg = json.dumps({"command": "subscribe"}) + "\n"
                sock.sendall(msg.encode())

                # Read subscription confirmation
                sock.recv(4096)

                # Stream events
                sock.settimeout(None)  # Block on reads
                buffer = b""

                while self._running:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    buffer += chunk

                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        try:
                            data = json.loads(line.decode().strip())
                            event_data = data.get("event", {})
                            event_name = event_data.get("event", "")

                            if event_name in event_map:
                                py_event = event_map[event_name]
                                event_bus.publish(
                                    py_event,
                                    source="rust_daemon",
                                    **event_data.get("data", {}),
                                )
                        except (json.JSONDecodeError, KeyError) as exc:
                            logger.debug("Event parse error: %s", exc)

                sock.close()

            except (socket.error, OSError) as exc:
                logger.debug("Event stream error: %s", exc)

            # Reconnect delay
            if self._running:
                time.sleep(2.0)


def start_daemon(
    socket_path: Optional[str] = None,
    probe_url: Optional[str] = None,
    interval: Optional[int] = None,
) -> Optional[subprocess.Popen]:
    """Start the Rust daemon as a subprocess.

    Args:
        socket_path: IPC socket path.
        probe_url: Connectivity probe URL.
        interval: Poll interval in seconds.

    Returns:
        Popen process handle, or None if binary not found.
    """
    binary = _find_daemon_binary()
    if not binary:
        logger.error("captivity-daemon binary not found")
        return None

    cmd = [binary]
    if socket_path:
        cmd.extend(["--socket", socket_path])
    if probe_url:
        cmd.extend(["--probe-url", probe_url])
    if interval:
        cmd.extend(["--interval", str(interval)])

    logger.info("Starting Rust daemon: %s", " ".join(cmd))

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        # Give it a moment to start
        time.sleep(0.5)
        if proc.poll() is not None:
            stderr = proc.stderr.read().decode() if proc.stderr else ""
            logger.error("Daemon exited immediately: %s", stderr)
            return None
        return proc
    except OSError as exc:
        logger.error("Failed to start daemon: %s", exc)
        return None
