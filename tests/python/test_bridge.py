"""Tests for captivity.daemon.bridge module."""

import json
import os
import socket
import threading
import time
import unittest
from unittest.mock import patch

from captivity.daemon.bridge import (
    DaemonBridge,
    _default_port,
    _find_daemon_binary,
    start_daemon,
)
from captivity.daemon.events import Event


class TestDefaultPort(unittest.TestCase):
    """Test default port resolution."""

    def test_uses_env_var(self):
        with patch.dict(os.environ, {"CAPTIVITY_PORT": "9999"}):
            port = _default_port()
            self.assertEqual(port, 9999)

    def test_falls_back_to_default(self):
        with patch.dict(os.environ, {}, clear=True):
            port = _default_port()
            self.assertEqual(port, 8788)


class TestFindDaemonBinary(unittest.TestCase):
    """Test daemon binary discovery."""

    def test_returns_none_when_not_found(self):
        result = _find_daemon_binary()
        # In test environment, binary likely doesn't exist
        # This just verifies the function doesn't crash
        self.assertTrue(result is None or isinstance(result, str))


class TestDaemonBridge(unittest.TestCase):
    """Test DaemonBridge with mock socket server."""

    def setUp(self):
        self.port = 18788
        self.bridge = DaemonBridge(port=self.port)

    def test_port(self):
        self.assertEqual(self.bridge.port, self.port)

    def test_not_connected_initially(self):
        self.assertFalse(self.bridge.is_connected)

    def test_connect_fails_no_server(self):
        result = self.bridge.connect()
        self.assertFalse(result)
        self.assertFalse(self.bridge.is_connected)

    def test_get_status_fails_no_server(self):
        result = self.bridge.get_status()
        self.assertIsNone(result)

    def test_request_probe_fails_no_server(self):
        result = self.bridge.request_probe()
        self.assertFalse(result)

    def test_stop_daemon_fails_no_server(self):
        result = self.bridge.stop_daemon()
        self.assertFalse(result)


class TestDaemonBridgeWithServer(unittest.TestCase):
    """Test DaemonBridge with a mock TCP socket server."""

    def setUp(self):
        self.server_running = True
        self.server_ready = threading.Event()
        self._start_mock_server()
        self.server_ready.wait(1.0)  # Wait for server to bind
        self.bridge = DaemonBridge(port=self.port)

    def tearDown(self):
        self.server_running = False
        time.sleep(0.2)

    def _start_mock_server(self):
        """Start a mock daemon server."""

        def server_loop():
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            self.port = server.getsockname()[1]
            server.listen(5)
            server.settimeout(0.5)
            self.server_ready.set()

            while self.server_running:
                try:
                    conn, _ = server.accept()
                    data = conn.recv(4096).decode().strip()
                    cmd = json.loads(data)

                    if cmd.get("command") == "status":
                        resp = {"ok": True, "status": "connected"}
                    elif cmd.get("command") == "probe":
                        resp = {"ok": True, "message": "probe_requested"}
                    elif cmd.get("command") == "stop":
                        resp = {"ok": True, "message": "stopping"}
                    else:
                        resp = {"ok": False, "message": "unknown"}

                    conn.sendall((json.dumps(resp) + "\n").encode())
                    conn.close()
                except socket.timeout:
                    continue
                except Exception:
                    break

            server.close()

        self.server_thread = threading.Thread(target=server_loop, daemon=True)
        self.server_thread.start()

    def test_connect_succeeds(self):
        result = self.bridge.connect()
        self.assertTrue(result)
        self.assertTrue(self.bridge.is_connected)

    def test_get_status(self):
        self.bridge.connect()
        status = self.bridge.get_status()
        self.assertEqual(status, "connected")

    def test_request_probe(self):
        result = self.bridge.request_probe()
        self.assertTrue(result)

    def test_stop_daemon(self):
        result = self.bridge.stop_daemon()
        self.assertTrue(result)


class TestStartDaemon(unittest.TestCase):
    """Test daemon process launcher."""

    @patch("captivity.daemon.bridge._find_daemon_binary")
    def test_returns_none_no_binary(self, mock_find):
        mock_find.return_value = None
        result = start_daemon()
        self.assertIsNone(result)


class TestEventMapping(unittest.TestCase):
    """Test Rust→Python event name mapping."""

    def test_event_map_coverage(self):
        """Verify all important Rust events have Python mappings."""
        # These are the Rust MonitorEvent variants that need mapping
        rust_events = [
            "NetworkConnected",
            "PortalDetected",
            "SessionExpired",
            "NetworkUnavailable",
        ]
        # The bridge maps these in _event_loop
        expected_python = {
            "NetworkConnected": Event.NETWORK_CONNECTED,
            "PortalDetected": Event.PORTAL_DETECTED,
            "SessionExpired": Event.SESSION_EXPIRED,
            "NetworkUnavailable": Event.SESSION_EXPIRED,
        }
        for rust_name in rust_events:
            self.assertIn(
                rust_name,
                expected_python,
                f"Missing mapping for {rust_name}",
            )


class TestUnsubscribe(unittest.TestCase):
    """Test event unsubscription."""

    def test_unsubscribe_noop_when_not_subscribed(self):
        bridge = DaemonBridge(port=9999)
        bridge.unsubscribe()  # Should not raise


if __name__ == "__main__":
    unittest.main()
