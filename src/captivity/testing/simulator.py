"""
Captive portal simulator for plugin testing.

Emulates common captive portal behaviors using stdlib http.server:
  - Login page with configurable HTML forms
  - HTTP redirect chains (302) for portal detection probes
  - Session management with configurable expiry
  - Rate limiting on login attempts
  - Intentional failure simulation (flaky portals)
  - Configurable response latency
  - Connectivity probe endpoint (204 when logged in)

Usage:
    from captivity.testing import PortalSimulator, SCENARIOS
    sim = PortalSimulator(scenario=SCENARIOS["simple"], port=9090)
    sim.start()  # starts in background thread
    # ... run tests against http://localhost:9090 ...
    sim.stop()
"""

import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
from urllib.parse import parse_qs

from captivity.testing.scenarios import Scenario, SCENARIOS
from captivity.utils.logging import get_logger

logger = get_logger("simulator")


def _login_page_html(scenario: Scenario) -> str:
    """Generate login page HTML for a scenario."""
    fields = []
    for name, default in scenario.form_fields.items():
        if name == scenario.password_field:
            fields.append(
                f'  <label>{name}</label>'
                f'  <input type="password" name="{name}" value="{default}">'
            )
        elif "terms" in name.lower():
            fields.append(
                f'  <label><input type="checkbox" name="{name}"> '
                f'I accept the terms</label>'
            )
        else:
            fields.append(
                f'  <label>{name}</label>'
                f'  <input type="text" name="{name}" value="{default}">'
            )

    fields_html = "\n".join(fields)
    return f"""<!DOCTYPE html>
<html>
<head><title>{scenario.portal_title}</title></head>
<body>
<h1>{scenario.portal_title}</h1>
<form method="POST" action="/login">
{fields_html}
  <button type="submit">Login</button>
</form>
</body>
</html>"""


def _success_html(scenario: Scenario) -> str:
    """Generate success page HTML."""
    return f"""<!DOCTYPE html>
<html>
<head><title>Success</title></head>
<body>
<h1>{scenario.success_text}</h1>
<p>You are now connected to the internet.</p>
</body>
</html>"""


class _SimulatorState:
    """Mutable state for the simulator."""

    def __init__(self) -> None:
        self.sessions: dict[str, float] = {}  # token → login time
        self.attempt_count: int = 0
        self.attempt_times: list[float] = []
        self.lock = threading.Lock()

    def reset(self) -> None:
        with self.lock:
            self.sessions.clear()
            self.attempt_count = 0
            self.attempt_times.clear()


class _PortalHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the portal simulator."""

    scenario: Scenario
    sim_state: _SimulatorState

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default logging."""
        pass

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.scenario.latency_ms > 0:
            time.sleep(self.scenario.latency_ms / 1000.0)

        if self.path == "/generate_204" or self.path == "/check":
            self._handle_probe()
        elif self.path == "/login" or self.path == "/":
            self._serve_login_page()
        elif self.path == "/status":
            self._serve_status()
        elif self.path == "/api/scenario":
            self._serve_scenario_info()
        else:
            self._redirect_to_login()

    def do_POST(self) -> None:
        """Handle POST requests (login submission)."""
        if self.scenario.latency_ms > 0:
            time.sleep(self.scenario.latency_ms / 1000.0)

        if self.path == "/login":
            self._handle_login()
        else:
            self.send_error(404)

    def _handle_probe(self) -> None:
        """Handle connectivity probe requests."""
        # Check if any session is active
        with self.sim_state.lock:
            active = self._has_active_session()

        if active:
            # Internet is available — return 204
            self.send_response(204)
            self.end_headers()
        else:
            # Redirect to login page (portal detected)
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()

    def _serve_login_page(self) -> None:
        """Serve the login form HTML."""
        html = _login_page_html(self.scenario)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html.encode())

    def _handle_login(self) -> None:
        """Process login form submission."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()
        params = parse_qs(body)

        with self.sim_state.lock:
            self.sim_state.attempt_count += 1
            self.sim_state.attempt_times.append(time.time())
            attempt = self.sim_state.attempt_count

            # Rate limiting check
            if self.scenario.rate_limit > 0:
                cutoff = time.time() - 60
                recent = [t for t in self.sim_state.attempt_times if t > cutoff]
                self.sim_state.attempt_times = recent
                if len(recent) > self.scenario.rate_limit:
                    self._send_html(
                        429,
                        "<h1>Too Many Requests</h1>"
                        "<p>Please wait before trying again.</p>",
                    )
                    logger.debug("Rate limited attempt %d", attempt)
                    return

            # Intentional failure simulation
            if (self.scenario.fail_first_n > 0 and
                    attempt <= self.scenario.fail_first_n):
                self._send_html(
                    403,
                    "<h1>Login Failed</h1>"
                    "<p>Invalid credentials. Please try again.</p>",
                )
                logger.debug(
                    "Intentional failure %d/%d",
                    attempt, self.scenario.fail_first_n,
                )
                return

            # Terms check
            if self.scenario.require_terms:
                if "accept_terms" not in params:
                    self._send_html(
                        400,
                        "<h1>Terms Required</h1>"
                        "<p>You must accept the terms.</p>",
                    )
                    return

            # Credential validation (accept any non-empty credentials)
            ufield = self.scenario.username_field
            if ufield and ufield not in params:
                self._send_html(
                    400,
                    f"<h1>Missing Field</h1><p>{ufield} is required.</p>",
                )
                return

            # Login succeeds — create session
            token = f"session-{attempt}-{int(time.time())}"
            self.sim_state.sessions[token] = time.time()

            logger.info("Login success (attempt %d, token=%s)", attempt, token)

            html = _success_html(self.scenario)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(html)))
            self.send_header("Set-Cookie", f"session={token}; Path=/")
            self.end_headers()
            self.wfile.write(html.encode())

    def _serve_status(self) -> None:
        """Serve simulator status as JSON."""
        with self.sim_state.lock:
            active = self._has_active_session()
            data = {
                "scenario": self.scenario.name,
                "connected": active,
                "total_attempts": self.sim_state.attempt_count,
                "active_sessions": len(self.sim_state.sessions),
            }
        body = json.dumps(data)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body.encode())

    def _serve_scenario_info(self) -> None:
        """Serve scenario configuration as JSON."""
        data = {
            "name": self.scenario.name,
            "description": self.scenario.description,
            "portal_title": self.scenario.portal_title,
            "form_fields": list(self.scenario.form_fields.keys()),
            "session_duration": self.scenario.session_duration,
            "require_terms": self.scenario.require_terms,
            "rate_limit": self.scenario.rate_limit,
            "fail_first_n": self.scenario.fail_first_n,
            "latency_ms": self.scenario.latency_ms,
        }
        body = json.dumps(data)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body.encode())

    def _redirect_to_login(self) -> None:
        """Redirect unknown paths to the login page."""
        self.send_response(302)
        self.send_header("Location", "/login")
        self.end_headers()

    def _has_active_session(self) -> bool:
        """Check if any session is active (within duration)."""
        if not self.sim_state.sessions:
            return False
        if self.scenario.session_duration <= 0:
            return True  # No expiry
        now = time.time()
        # Expire old sessions
        expired = [
            k for k, v in self.sim_state.sessions.items()
            if now - v > self.scenario.session_duration
        ]
        for k in expired:
            del self.sim_state.sessions[k]
        return len(self.sim_state.sessions) > 0

    def _send_html(self, code: int, body_html: str) -> None:
        """Send an HTML response."""
        html = f"<!DOCTYPE html><html><body>{body_html}</body></html>"
        self.send_response(code)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html.encode())


class PortalSimulator:
    """Captive portal simulator for testing.

    Creates a local HTTP server that emulates captive portal
    behavior according to a configurable Scenario.

    Attributes:
        scenario: Active test scenario.
        port: HTTP server port.
        host: Server bind address.
    """

    def __init__(
        self,
        scenario: Optional[Scenario] = None,
        port: int = 9090,
        host: str = "127.0.0.1",
    ) -> None:
        self.scenario = scenario or SCENARIOS["simple"]
        self.port = port
        self.host = host
        self._state = _SimulatorState()
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the simulator in a background thread."""
        handler = type(
            "Handler",
            (_PortalHandler,),
            {"scenario": self.scenario, "sim_state": self._state},
        )
        self._server = HTTPServer((self.host, self.port), handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Portal simulator started at http://%s:%d (scenario: %s)",
            self.host, self.port, self.scenario.name,
        )

    def stop(self) -> None:
        """Stop the simulator."""
        if self._server:
            self._server.shutdown()
            self._server = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Portal simulator stopped")

    def reset(self) -> None:
        """Reset simulator state (sessions, attempt counts)."""
        self._state.reset()

    def set_scenario(self, scenario: Scenario) -> None:
        """Change the active scenario.

        Requires restart for changes to take effect.
        """
        self.scenario = scenario
        self.reset()

    @property
    def url(self) -> str:
        """Base URL of the simulator."""
        return f"http://{self.host}:{self.port}"

    @property
    def is_running(self) -> bool:
        """Whether the simulator is currently running."""
        return self._thread is not None and self._thread.is_alive()

    def __enter__(self) -> "PortalSimulator":
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()

    def __repr__(self) -> str:
        status = "running" if self.is_running else "stopped"
        return (
            f"PortalSimulator(scenario={self.scenario.name!r}, "
            f"port={self.port}, {status})"
        )
