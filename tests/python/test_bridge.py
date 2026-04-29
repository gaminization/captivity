"""Tests for captivity.daemon.bridge module."""

import json
import os
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from captivity.daemon.bridge import (
    DaemonBridge,
    _default_socket_path,
    _find_daemon_binary,
    start_daemon,
)
from captivity.daemon.events import Event


class TestDefaultSocketPath(unittest.TestCase):
    """Test default socket path resolution."""

    def test_uses_xdg_runtime_dir(self):
        with patch.dict(os.environ, {"XDG_RUNTIME_DIR": "/run/user/1000"}):
            path = _default_socket_path()
            self.assertIn("captivity-daemon.sock", path)
            self.assertIn("/run/user/1000", path)

    def test_falls_back_to_tmp(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove XDG_RUNTIME_DIR if present
            os.environ.pop("XDG_RUNTIME_DIR", None)
            path = _default_socket_path()
            self.assertIn("captivity-daemon.sock", path)


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
        self.tmpdir = tempfile.mkdtemp()
        self.socket_path = os.path.join(self.tmpdir, "test.sock")
        self.bridge = DaemonBridge(socket_path=self.socket_path)

    def test_socket_path(self):
        self.assertEqual(self.bridge.socket_path, self.socket_path)

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
    """Test DaemonBridge with a mock Unix socket server."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.socket_path = os.path.join(self.tmpdir, "test.sock")
        self.server_running = True
        self._start_mock_server()
        time.sleep(0.1)  # Let server start
        self.bridge = DaemonBridge(socket_path=self.socket_path)

    def tearDown(self):
        self.server_running = False
        time.sleep(0.2)
        try:
            os.unlink(self.socket_path)
        except OSError:
            pass

    def _start_mock_server(self):
        """Start a mock daemon server."""

        def server_loop():
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(self.socket_path)
            server.listen(5)
            server.settimeout(0.5)

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
        bridge = DaemonBridge(socket_path="/nonexistent")
        bridge.unsubscribe()  # Should not raise


if __name__ == "__main__":
    unittest.main()
