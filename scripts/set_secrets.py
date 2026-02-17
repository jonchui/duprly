#!/usr/bin/env python3
"""
Store DUPRLY secrets in the system keychain (macOS Keychain).
Run from repo root: python3 scripts/set_secrets.py

Values are read from .env first; keychain is used when you want to avoid
storing secrets in plain text. After running, you can remove sensitive
values from .env and they will be read from keychain.
"""
import os
import sys
import getpass

# Run from repo root so duprly_secrets and .env are found
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)

from duprly_secrets import set_secret, get_secret


def prompt(key: str, default: str = "", mask: bool = True) -> str:
    """Prompt for a value; empty keeps existing keychain value or default."""
    current = get_secret(key) or default
    if current and mask:
        hint = "(current keychain value set, leave blank to keep)"
    elif default:
        hint = f"(default: {default})"
    else:
        hint = "(leave blank to skip)"
    label = "Password" if mask else "Value"
    if mask:
        raw = getpass.getpass(f"  {key} [{label}] {hint}: ").strip()
    else:
        raw = input(f"  {key} [{label}] {hint}: ").strip()
    if raw:
        return raw
    if current:
        return current
    return default


def main():
    print("DUPRLY: Store secrets in system keychain (macOS Keychain)\n")
    try:
        import keyring  # noqa: F401
    except ImportError:
        print("Install keyring first: pip install keyring")
        print("Then run this script again.")
        sys.exit(1)

    print("Enter values to store in keychain. Leave blank to keep existing or skip.\n")

    for key in ("DUPR_USERNAME", "DUPR_PASSWORD", "DUPR_CLUB_ID", "MCP_API_KEY"):
        value = prompt(key, mask=(key in ("DUPR_PASSWORD", "MCP_API_KEY")))
        if value:
            set_secret(key, value)
            print(f"  -> Stored {key} in keychain.")
        else:
            if get_secret(key):
                print(f"  -> Kept existing {key} in keychain.")
            else:
                print(f"  -> Skipped {key}.")

    print("\nDone. Restart the MCP server to use keychain values.")


if __name__ == "__main__":
    main()
