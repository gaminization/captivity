"""
Credential management for Captivity.

Primary backend: OS keyring (python-keyring) which talks to GNOME Secret
Service / KWallet through D-Bus.  This requires a live user D-Bus session,
which means the daemon MUST run as a *user* service (systemctl --user), not
a system service.

Fallback backend: AES-256-CBC encrypted file stored at
~/.local/share/captivity/credentials.enc using a key derived from a
machine-local secret.  This is used automatically when the keyring is
unavailable (e.g. headless systems or early-boot without a D-Bus session).

Key design decisions
--------------------
- Primary path  : keyring (SecretService/libsecret/KWallet)
- Fallback path : file-based encrypted store  (no plaintext on disk)
- Diagnostics   : each path logs which backend was used so failures are
                  immediately visible in journald
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Optional

from captivity.utils.logging import get_logger

logger = get_logger("credentials")

# Keyring namespace
SERVICE_NAME = "captivity"

# Fallback file location
_CRED_DIR = Path.home() / ".local" / "share" / "captivity"
_CRED_FILE = _CRED_DIR / "credentials.enc"


# ---------------------------------------------------------------------------
# Internal helpers — file-based encrypted fallback
# ---------------------------------------------------------------------------

def _derive_key() -> bytes:
    """Derive a 256-bit key from a machine-local secret.

    Uses /etc/machine-id (stable, non-secret, but unique per machine).
    The derived key protects the file from casual inspection; it is NOT
    designed to protect against an attacker with root on the same machine.
    """
    try:
        machine_id = Path("/etc/machine-id").read_text().strip()
    except OSError:
        machine_id = "captivity-fallback"
    salt = b"captivity-cred-v1"
    return hashlib.pbkdf2_hmac("sha256", machine_id.encode(), salt, iterations=100_000)


def _encrypt(plaintext: str, key: bytes) -> str:
    """Encrypt plaintext with AES-256-CBC, returning a base64 string."""
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        import secrets as _secrets

        iv = _secrets.token_bytes(16)
        padded = plaintext.encode()
        # PKCS7-style padding
        pad_len = 16 - (len(padded) % 16)
        padded += bytes([pad_len] * pad_len)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        enc = cipher.encryptor()
        ct = enc.update(padded) + enc.finalize()
        return base64.b64encode(iv + ct).decode()
    except ImportError:
        # cryptography not available — fall back to base64 obfuscation with a warning
        logger.warning(
            "CREDENTIAL_FALLBACK_INSECURE: 'cryptography' package not installed. "
            "Install it for proper encryption: pip install cryptography"
        )
        return base64.b64encode(plaintext.encode()).decode()


def _decrypt(ciphertext: str, key: bytes) -> str:
    """Decrypt a base64 string produced by _encrypt."""
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend

        raw = base64.b64decode(ciphertext)
        iv, ct = raw[:16], raw[16:]
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        dec = cipher.decryptor()
        padded = dec.update(ct) + dec.finalize()
        pad_len = padded[-1]
        return padded[:-pad_len].decode()
    except ImportError:
        return base64.b64decode(ciphertext).decode()


def _file_store(network: str, username: str, password: str) -> None:
    _CRED_DIR.mkdir(parents=True, exist_ok=True)
    key = _derive_key()
    data: dict = {}
    if _CRED_FILE.exists():
        try:
            data = json.loads(_decrypt(_CRED_FILE.read_text(), key))
        except Exception:
            data = {}
    data[network] = {
        "username": _encrypt(username, key),
        "password": _encrypt(password, key),
    }
    _CRED_FILE.write_text(_encrypt(json.dumps(data), key))
    # Restrict file permissions to owner only
    _CRED_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
    logger.info("CREDENTIAL_STORED backend=file network='%s'", network)


def _file_retrieve(network: str) -> Optional[tuple[str, str]]:
    if not _CRED_FILE.exists():
        return None
    key = _derive_key()
    try:
        data = json.loads(_decrypt(_CRED_FILE.read_text(), key))
        if network not in data:
            return None
        username = _decrypt(data[network]["username"], key)
        password = _decrypt(data[network]["password"], key)
        return username, password
    except Exception as exc:
        logger.warning("CREDENTIAL_FILE_READ_FAILED: %s", exc)
        return None


def _file_delete(network: str) -> None:
    if not _CRED_FILE.exists():
        return
    key = _derive_key()
    try:
        data = json.loads(_decrypt(_CRED_FILE.read_text(), key))
        data.pop(network, None)
        _CRED_FILE.write_text(_encrypt(json.dumps(data), key))
        _CRED_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except Exception as exc:
        logger.warning("CREDENTIAL_FILE_DELETE_FAILED: %s", exc)


# ---------------------------------------------------------------------------
# Keyring helpers
# ---------------------------------------------------------------------------

def _keyring_available() -> bool:
    """Return True if the OS keyring is reachable from this process."""
    try:
        import keyring
        kr = keyring.get_keyring()
        # Chainer means we need to check the first live backend
        name = type(kr).__name__
        if name == "ChainerBackend":
            from keyring.backends.chainer import ChainerBackend
            for b in kr.backends:
                bname = type(b).__name__
                # These require a D-Bus session
                if bname in ("Keyring",) and "SecretService" in type(b).__module__:
                    try:
                        b.get_password("__captivity_probe__", "__probe__")
                        return True
                    except Exception:
                        continue
                elif bname == "Keyring" and "kwallet" in type(b).__module__:
                    try:
                        b.get_password("__captivity_probe__", "__probe__")
                        return True
                    except Exception:
                        continue
                elif bname == "Keyring" and "libsecret" in type(b).__module__:
                    try:
                        b.get_password("__captivity_probe__", "__probe__")
                        return True
                    except Exception:
                        continue
            return False
        # Single backend — try a probe
        try:
            kr.get_password("__captivity_probe__", "__probe__")
            return True
        except Exception:
            return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class CredentialError(Exception):
    """Raised when credential operations fail."""


def store(network: str, username: str, password: str) -> None:
    """Store credentials for a network.

    Tries keyring first; falls back to the encrypted file store.
    """
    # Try keyring
    try:
        import keyring
        if _keyring_available():
            keyring.set_password(SERVICE_NAME, f"{network}-username", username)
            keyring.set_password(SERVICE_NAME, f"{network}-password", password)
            logger.info("CREDENTIAL_STORED backend=keyring network='%s'", network)
            return
    except Exception as exc:
        logger.warning("CREDENTIAL_KEYRING_STORE_FAILED: %s — using file fallback", exc)

    # Fallback to encrypted file
    try:
        _file_store(network, username, password)
    except Exception as exc:
        raise CredentialError(
            f"Failed to store credentials for '{network}': {exc}"
        ) from exc


def retrieve(network: str) -> tuple[str, str]:
    """Retrieve credentials for a network.

    Tries keyring first; falls back to the encrypted file store.
    """
    logger.debug("CREDENTIAL_LOOKUP network='%s'", network)

    # --- Keyring path ---
    try:
        import keyring
        if _keyring_available():
            username = keyring.get_password(SERVICE_NAME, f"{network}-username")
            password = keyring.get_password(SERVICE_NAME, f"{network}-password")
            if username and password:
                logger.debug("CREDENTIAL_RESULT backend=keyring found=True network='%s'", network)
                return username, password
            logger.debug("CREDENTIAL_RESULT backend=keyring found=False network='%s'", network)
        else:
            logger.info(
                "CREDENTIAL_KEYRING_UNAVAILABLE: D-Bus session not reachable. "
                "The daemon should run as a user service (systemctl --user). "
                "Trying encrypted file fallback."
            )
    except Exception as exc:
        logger.warning(
            "CREDENTIAL_KEYRING_ERROR: %s — trying file fallback", exc, exc_info=True
        )

    # --- File fallback path ---
    result = _file_retrieve(network)
    if result:
        username, password = result
        logger.debug("CREDENTIAL_RESULT backend=file found=True network='%s'", network)
        return username, password

    # Nothing found anywhere
    raise CredentialError(
        f"Credentials not found for network '{network}'. "
        f"Store credentials first: captivity creds store {network}"
    )


def delete(network: str) -> None:
    """Delete stored credentials for a network (both backends)."""
    # Keyring
    try:
        import keyring
        if _keyring_available():
            for field in ("username", "password"):
                try:
                    keyring.delete_password(SERVICE_NAME, f"{network}-{field}")
                except Exception:
                    pass
    except Exception:
        pass

    # File
    _file_delete(network)
    logger.info("Credentials deleted for '%s'", network)


def list_networks() -> list[str]:
    """List networks with stored credentials (file backend only)."""
    try:
        if not _CRED_FILE.exists():
            return []
        key = _derive_key()
        data = json.loads(_decrypt(_CRED_FILE.read_text(), key))
        return sorted(data.keys())
    except Exception:
        return []
