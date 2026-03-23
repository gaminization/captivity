"""
Test scenario definitions for the portal simulator.

Each scenario defines a portal behavior that the simulator
can emulate: login pages, redirect patterns, session expiry,
rate limiting, and network failures.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Scenario:
    """A captive portal test scenario.

    Attributes:
        name: Scenario identifier.
        description: Human-readable description.
        portal_title: Title shown on the login page HTML.
        form_fields: Dict of field name → default value for the login form.
        redirect_url: URL the portal redirects to before login.
        success_text: Text returned on successful login.
        session_duration: Seconds before session expires (0 = never).
        require_terms: Whether the form includes a terms checkbox.
        rate_limit: Max login attempts per minute (0 = unlimited).
        fail_first_n: Fail the first N login attempts intentionally.
        latency_ms: Simulated response latency in milliseconds.
        username_field: Name of the username form field.
        password_field: Name of the password form field.
    """
    name: str
    description: str = ""
    portal_title: str = "WiFi Login"
    form_fields: dict[str, str] = field(default_factory=lambda: {
        "username": "",
        "password": "",
    })
    redirect_url: str = "http://captive.portal/login"
    success_text: str = "Login successful"
    session_duration: int = 0
    require_terms: bool = False
    rate_limit: int = 0
    fail_first_n: int = 0
    latency_ms: int = 0
    username_field: str = "username"
    password_field: str = "password"


# Built-in test scenarios
SCENARIOS: dict[str, Scenario] = {
    "simple": Scenario(
        name="simple",
        description="Basic username/password portal with no complications",
        portal_title="Simple WiFi Login",
    ),

    "terms": Scenario(
        name="terms",
        description="Portal requiring terms acceptance checkbox",
        portal_title="WiFi Login — Terms Required",
        require_terms=True,
        form_fields={
            "username": "",
            "password": "",
            "accept_terms": "on",
        },
    ),

    "redirect": Scenario(
        name="redirect",
        description="Portal with HTTP redirect chain before login page",
        portal_title="Redirected Portal",
        redirect_url="http://gateway.example.com/redirect?url=http://captive.portal/login",
    ),

    "session_expiry": Scenario(
        name="session_expiry",
        description="Portal where sessions expire after 30 seconds",
        portal_title="Session-Limited Portal",
        session_duration=30,
    ),

    "rate_limited": Scenario(
        name="rate_limited",
        description="Portal that rate-limits login attempts to 3/min",
        portal_title="Rate-Limited Portal",
        rate_limit=3,
    ),

    "flaky": Scenario(
        name="flaky",
        description="Portal that fails the first 2 login attempts then succeeds",
        portal_title="Flaky Portal",
        fail_first_n=2,
    ),

    "slow": Scenario(
        name="slow",
        description="Portal with 2-second response latency",
        portal_title="Slow Portal",
        latency_ms=2000,
    ),

    "custom_fields": Scenario(
        name="custom_fields",
        description="Portal with non-standard field names",
        portal_title="Custom Fields Portal",
        username_field="user_email",
        password_field="user_pass",
        form_fields={
            "user_email": "",
            "user_pass": "",
            "zone": "guest",
        },
    ),

    "email_only": Scenario(
        name="email_only",
        description="Portal requiring only email (no password)",
        portal_title="Email Registration Portal",
        username_field="email",
        password_field="",
        form_fields={
            "email": "",
        },
    ),
}
