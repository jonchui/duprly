"""
Read/write DUPRLY secrets from environment or macOS Keychain (via keyring).
Secrets are looked up in order: os.environ (from .env) then keyring service "duprly".
"""
import os
from typing import Optional

# Load .env so os.getenv sees DUPR_* and MCP_API_KEY from file
def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

_load_env()

_KEYRING_SERVICE = "duprly"


def get_secret(key: str) -> Optional[str]:
    """Return value for key from env or keychain. None if not set."""
    value = os.getenv(key)
    if value is not None and value.strip():
        return value.strip()
    try:
        import keyring
        value = keyring.get_password(_KEYRING_SERVICE, key)
        return value
    except Exception:
        return None


def set_secret(key: str, value: str) -> None:
    """Store secret in system keychain (macOS Keychain when keyring is used)."""
    try:
        import keyring
        keyring.set_password(_KEYRING_SERVICE, key, value)
    except Exception as e:
        raise RuntimeError(
            f"Could not store secret in keychain. Install keyring: pip install keyring. Error: {e}"
        ) from e


def delete_secret(key: str) -> bool:
    """Remove secret from keychain. Returns True if deleted."""
    try:
        import keyring
        keyring.delete_password(_KEYRING_SERVICE, key)
        return True
    except Exception:
        return False
