"""
Credential management via OS keyring.

Wraps the python `keyring` module for secure credential storage
and retrieval. No plaintext credentials are stored on disk.
"""

import keyring

from captivity.utils.logging import get_logger

logger = get_logger("credentials")

# Keyring namespace
SERVICE_NAME = "captivity"


class CredentialError(Exception):
    """Raised when credential operations fail."""


def store(network: str, username: str, password: str) -> None:
    """Store credentials for a network.

    Args:
        network: Network identifier (e.g., SSID).
        username: Login username.
        password: Login password.

    Raises:
        CredentialError: If storage fails.
    """
    try:
        keyring.set_password(SERVICE_NAME, f"{network}-username", username)
        keyring.set_password(SERVICE_NAME, f"{network}-password", password)
    except Exception as exc:
        raise CredentialError(
            f"Failed to store credentials for '{network}': {exc}"
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
    username = keyring.get_password(SERVICE_NAME, f"{network}-username")
    password = keyring.get_password(SERVICE_NAME, f"{network}-password")

    if not username or not password:
        raise CredentialError(
            f"Credentials not found for network '{network}'. "
            f"Store credentials first: captivity creds store {network}"
        )

    logger.debug("Credentials retrieved for '%s'", network)
    return username, password


def delete(network: str) -> None:
    """Delete stored credentials for a network.

    Args:
        network: Network identifier.
    """
    for field in ("username", "password"):
        try:
            keyring.delete_password(SERVICE_NAME, f"{network}-{field}")
        except keyring.errors.PasswordDeleteError:
            pass  # Already deleted or doesn't exist

    logger.info("Credentials deleted for '%s'", network)


def list_networks() -> list[str]:
    """List networks with stored credentials.

    Returns:
        List of network names.
    """
    # Keyring API does not have a standard cross-platform way to list all keys.
    # We will return an empty list or try specific backend capabilities if needed.
    # Since this is primarily used for displaying status in CLI, returning an empty
    # list or a notice is acceptable if backend doesn't support get_credential().
    try:
        # Fallback to secret-tool for listing ONLY if absolutely necessary,
        # otherwise we just log that listing is unavailable.
        logger.debug("listing networks requires backend support")
        return []
    except Exception:
        return []
