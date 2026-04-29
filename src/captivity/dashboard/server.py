"""
Embedded HTTP server for the Captivity web dashboard.

Serves a single-page HTML dashboard and JSON API endpoints
at http://localhost:8787. Uses Python's built-in http.server
module — zero external dependencies.

Binds only to localhost for security.
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from captivity.dashboard.api import DashboardAPI
from captivity.dashboard.page import DASHBOARD_HTML
from captivity.utils.logging import get_logger

logger = get_logger("dashboard.server")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the dashboard.

    Serves the HTML dashboard at / and JSON API at /api/*.
    """

    api: DashboardAPI = None  # Set by DashboardServer

    def do_GET(self) -> None:
        """Handle GET requests."""
        # API endpoints
        if self.path.startswith("/api/"):
            self._handle_api()
            return

        # Dashboard page
        if self.path == "/" or self.path == "/index.html":
            self._send_response(200, "text/html", DASHBOARD_HTML)
            return

        # 404
        self._send_response(404, "text/plain", "Not Found")

    def _handle_api(self) -> None:
        """Route API requests."""
        result = self.api.handle_request(self.path)
        if result is not None:
            self._send_response(200, "application/json", result)
        else:
            self._send_response(
                404, "application/json", json.dumps({"error": "endpoint not found"})
            )

    def _send_response(self, code: int, content_type: str, body: str) -> None:
        """Send an HTTP response."""
        self.send_response(code)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args) -> None:
        """Suppress default access logging to keep output clean."""
        pass


class DashboardServer:
    """Manages the dashboard HTTP server lifecycle.

    Attributes:
        host: Bind address (default: 127.0.0.1).
        port: Port number (default: 8787).
        api: DashboardAPI instance.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        api: Optional[DashboardAPI] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.api = api or DashboardAPI()
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self, blocking: bool = True) -> None:
        """Start the dashboard server.

        Args:
            blocking: If True, blocks until shutdown. If False,
                     runs in a background thread.
        """
        DashboardHandler.api = self.api

        try:
            self._server = HTTPServer((self.host, self.port), DashboardHandler)
        except OSError as exc:
            logger.error("Failed to start dashboard: %s", exc)
            return

        logger.info("Dashboard at http://%s:%d", self.host, self.port)

        if blocking:
            try:
                self._server.serve_forever()
            except KeyboardInterrupt:
                self.stop()
        else:
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                daemon=True,
                name="captivity-dashboard",
            )
            self._thread.start()

    def stop(self) -> None:
        """Stop the dashboard server."""
        if self._server:
            self._server.shutdown()
            logger.info("Dashboard stopped")

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._thread is not None and self._thread.is_alive()
