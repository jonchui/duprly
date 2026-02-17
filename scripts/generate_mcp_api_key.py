#!/usr/bin/env python3
"""
Generate a unique MCP_API_KEY and store it (keychain if available, else .env).
Run from repo root: python3 scripts/generate_mcp_api_key.py

Then copy the key into Poke (Settings → Connections → your DUPRLY integration → API Key).
"""
import os
import secrets
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)


def main():
    key = secrets.token_urlsafe(32)

    # Prefer keychain
    try:
        from duprly_secrets import set_secret
        set_secret("MCP_API_KEY", key)
        where = "keychain"
    except Exception as e:
        # Fallback: append to .env
        env_path = os.path.join(REPO_ROOT, ".env")
        if not os.path.isfile(env_path):
            with open(env_path, "w") as f:
                f.write("# DUPRLY – created by generate_mcp_api_key.py\n")
        with open(env_path, "a") as f:
            f.write(f"\nMCP_API_KEY={key}\n")
        where = ".env"
        if "keyring" in str(e).lower():
            print("(keyring not installed; stored in .env instead. pip install keyring for keychain.)", file=sys.stderr)

    print("MCP_API_KEY generated and stored in", where + ".\n")
    print("Copy this key into Poke (Settings → Connections → DUPRLY → API Key):\n")
    print(key)
    print("\nRestart the MCP server (e.g. ./run.sh --sse --port 8000) for it to take effect.")


if __name__ == "__main__":
    main()
