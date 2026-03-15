"""
Credential management via Linux Secret Service.

Wraps the `secret-tool` CLI utility for secure credential storage
and retrieval. No plaintext credentials are stored on disk.
"""

import subprocess
import shutil
from typing import Optional

from captivity.utils.logging import get_logger

logger = get_logger("credentials")

# Secret-tool attributes for captivity credentials
ATTR_APP = "application"
ATTR_APP_VAL = "captivity"
ATTR_NETWORK = "network"
ATTR_FIELD = "field"


class CredentialError(Exception):
    """Raised when credential operations fail."""


def _check_secret_tool() -> None:
    """Verify that secret-tool is available."""
    if not shutil.which("secret-tool"):
        raise CredentialError(
            "secret-tool not found. Install libsecret-tools:\n"
            "  sudo apt install libsecret-tools    # Debian/Ubuntu\n"
            "  sudo dnf install libsecret           # Fedora\n"
            "  sudo pacman -S libsecret             # Arch"
        )


def store(network: str, username: str, password: str) -> None:
    """Store credentials for a network.

    Args:
        network: Network identifier (e.g., SSID).
        username: Login username.
        password: Login password.

    Raises:
        CredentialError: If storage fails.
    """
    _check_secret_tool()

    for field, value in [("username", username), ("password", password)]:
        try:
            subprocess.run(
                [
                    "secret-tool", "store",
                    "--label", f"captivity-{network}-{field}",
                    ATTR_APP, ATTR_APP_VAL,
                    ATTR_NETWORK, network,
                    ATTR_FIELD, field,
                ],
                input=value.encode(),
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            raise CredentialError(
                f"Failed to store {field} for '{network}': {exc.stderr.decode()}"
            ) from exc

    logger.info("Credentials stored for '%s'", network)


def retrieve(network: str) -> tuple[str, str]:
    """Retrieve credentials for a network.

    Args:
        network: Network identifier.

    Returns:
        Tuple of (username, password).

    Raises:
        CredentialError: If retrieval fails or credentials not found.
    """
    _check_secret_tool()

    results = {}
    for field in ("username", "password"):
        try:
            result = subprocess.run(
                [
                    "secret-tool", "lookup",
                    ATTR_APP, ATTR_APP_VAL,
                    ATTR_NETWORK, network,
                    ATTR_FIELD, field,
                ],
                capture_output=True,
                check=False,
            )
            value = result.stdout.decode().strip()
            if not value:
                raise CredentialError(
                    f"No {field} found for network '{network}'. "
                    f"Store credentials first: captivity creds store {network}"
                )
            results[field] = value
        except FileNotFoundError as exc:
            raise CredentialError("secret-tool not found") from exc

    logger.debug("Credentials retrieved for '%s'", network)
    return results["username"], results["password"]


def delete(network: str) -> None:
    """Delete stored credentials for a network.

    Args:
        network: Network identifier.
    """
    _check_secret_tool()

    for field in ("username", "password"):
        subprocess.run(
            [
                "secret-tool", "clear",
                ATTR_APP, ATTR_APP_VAL,
                ATTR_NETWORK, network,
                ATTR_FIELD, field,
            ],
            capture_output=True,
            check=False,
        )

    logger.info("Credentials deleted for '%s'", network)


def list_networks() -> list[str]:
    """List networks with stored credentials.

    Returns:
        List of network names.
    """
    _check_secret_tool()

    try:
        result = subprocess.run(
            [
                "secret-tool", "search", "--all",
                ATTR_APP, ATTR_APP_VAL,
            ],
            capture_output=True,
            check=False,
            text=True,
        )

        networks = set()
        for line in result.stdout.splitlines():
            if f"attribute.{ATTR_NETWORK}" in line:
                value = line.split("=", 1)[-1].strip()
                if value:
                    networks.add(value)

        return sorted(networks)

    except FileNotFoundError:
        return []
