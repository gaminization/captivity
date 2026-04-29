"""
Dynamic captive portal login page parser.

Parses HTML login pages to extract form fields, action URLs, and hidden
inputs. Enables automatic login to arbitrary captive portals without
hardcoded form structures.

Uses only Python stdlib (html.parser) — no external dependencies.
"""

import re
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin

import requests

from captivity.utils.logging import get_logger

logger = get_logger("parser")


class FormField:
    """Represents a single form input field.

    Attributes:
        name: Field name attribute.
        value: Field value attribute (default or pre-filled).
        field_type: Input type (text, password, hidden, submit, etc.).
        is_password: Whether this is a password field.
        is_username: Whether this is likely a username field.
    """

    USERNAME_PATTERNS = re.compile(
        r"(user|login|email|account|name|id|uid)", re.IGNORECASE
    )
    PASSWORD_PATTERNS = re.compile(r"(pass|pwd|secret|credential)", re.IGNORECASE)

    def __init__(
        self,
        name: str,
        value: str = "",
        field_type: str = "text",
    ) -> None:
        self.name = name
        self.value = value
        self.field_type = field_type.lower()

    @property
    def is_password(self) -> bool:
        """Check if this is a password field."""
        return self.field_type == "password" or bool(
            self.PASSWORD_PATTERNS.search(self.name)
        )

    @property
    def is_username(self) -> bool:
        """Check if this is likely a username/email field."""
        if self.field_type == "password":
            return False
        return self.field_type in ("text", "email") and bool(
            self.USERNAME_PATTERNS.search(self.name)
        )

    @property
    def is_hidden(self) -> bool:
        """Check if this is a hidden field."""
        return self.field_type == "hidden"

    def __repr__(self) -> str:
        return f"FormField(name={self.name!r}, type={self.field_type!r})"


class LoginForm:
    """Represents a parsed HTML login form.

    Attributes:
        action: Form action URL (submit endpoint).
        method: HTTP method (GET or POST).
        fields: List of form fields.
    """

    def __init__(
        self,
        action: str = "",
        method: str = "POST",
    ) -> None:
        self.action = action
        self.method = method.upper()
        self.fields: list[FormField] = []

    @property
    def username_field(self) -> Optional[FormField]:
        """Find the username field in the form."""
        for field in self.fields:
            if field.is_username:
                return field
        # Fallback: first text/email field
        for field in self.fields:
            if field.field_type in ("text", "email") and not field.is_hidden:
                return field
        return None

    @property
    def password_field(self) -> Optional[FormField]:
        """Find the password field in the form."""
        for field in self.fields:
            if field.is_password:
                return field
        return None

    def build_payload(self, username: str, password: str) -> dict:
        """Build the login form payload with injected credentials.

        Args:
            username: Username to inject.
            password: Password to inject.

        Returns:
            Dictionary of form field name/value pairs.
        """
        payload = {}

        for field in self.fields:
            if field.is_username:
                payload[field.name] = username
            elif field.is_password:
                payload[field.name] = password
            elif field.is_hidden or field.field_type == "submit":
                payload[field.name] = field.value
            # Skip other fields (checkboxes, etc.) unless they have values
            elif field.value:
                payload[field.name] = field.value

        return payload

    def __repr__(self) -> str:
        return (
            f"LoginForm(action={self.action!r}, method={self.method!r}, "
            f"fields={len(self.fields)})"
        )


class PortalHTMLParser(HTMLParser):
    """HTML parser that extracts login forms from portal pages."""

    def __init__(self) -> None:
        super().__init__()
        self.forms: list[LoginForm] = []
        self._current_form: Optional[LoginForm] = None
        self._in_form = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attr_dict = dict(attrs)

        if tag == "form":
            self._in_form = True
            self._current_form = LoginForm(
                action=attr_dict.get("action", ""),
                method=attr_dict.get("method", "POST"),
            )

        elif tag == "input" and self._in_form and self._current_form:
            name = attr_dict.get("name", "")
            if name:
                self._current_form.fields.append(
                    FormField(
                        name=name,
                        value=attr_dict.get("value", ""),
                        field_type=attr_dict.get("type", "text"),
                    )
                )

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._in_form and self._current_form:
            self.forms.append(self._current_form)
            self._current_form = None
            self._in_form = False


def find_login_form(forms: list[LoginForm]) -> Optional[LoginForm]:
    """Select the most likely login form from a list of forms.

    Prioritizes forms that have both username and password fields.

    Args:
        forms: List of parsed LoginForm objects.

    Returns:
        The best login form candidate, or None.
    """
    # Prefer forms with both username and password fields
    for form in forms:
        if form.username_field and form.password_field:
            return form

    # Fallback: any form with a password field
    for form in forms:
        if form.password_field:
            return form

    return forms[0] if forms else None


def parse_portal_page(
    url: str,
    timeout: int = 10,
) -> Optional[LoginForm]:
    """Fetch and parse a captive portal login page.

    Args:
        url: URL of the portal page.
        timeout: Request timeout in seconds.

    Returns:
        LoginForm if a login form was found, None otherwise.
    """
    try:
        logger.info("Fetching portal page: %s", url)
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.error("Failed to fetch portal page: %s", exc)
        return None

    parser = PortalHTMLParser()
    parser.feed(response.text)

    if not parser.forms:
        logger.warning("No forms found on portal page")
        return None

    form = find_login_form(parser.forms)

    if form:
        # Resolve relative action URLs
        if form.action and not form.action.startswith("http"):
            form.action = urljoin(url, form.action)
        elif not form.action:
            form.action = url

        logger.info(
            "Found login form: action=%s, fields=%d",
            form.action,
            len(form.fields),
        )

    return form
