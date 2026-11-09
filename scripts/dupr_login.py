"""
One-time DUPR sign-in for duprly on this Mac, now that DUPR emails a 6-digit code on login.

Signs in with DUPR_USERNAME / DUPR_PASSWORD from .env (or the keychain), asks you for the code,
and saves the token to ~/.duprly_config — where duprly's search and the web app already look.
DUPR tokens last about 30 days; run this again when search stops finding live players.

    python scripts/dupr_login.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from duprly_secrets import get_secret  # noqa: E402  (loads .env)
from web.services import dupr_live  # noqa: E402

CONFIG = os.path.expanduser("~/.duprly_config")


def save(token: str) -> None:
    fd = os.open(CONFIG, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"access_token": token}, f)
    os.chmod(CONFIG, 0o600)


def main() -> int:
    user, pw = get_secret("DUPR_USERNAME"), get_secret("DUPR_PASSWORD")
    if not user or not pw:
        print("Set DUPR_USERNAME and DUPR_PASSWORD in .env first.")
        return 1
    print(f"Signing in to DUPR as {user} …")
    r = dupr_live.start_login(user, pw)
    if not r:
        print("DUPR didn't accept that email and password.")
        return 1
    if r.get("token"):
        save(r["token"])
        print(f"✓ Signed in (no code needed). Token saved to {CONFIG}.")
        return 0
    challenge = r["challenge"]
    print(f"DUPR emailed a 6-digit code to {user}.")
    while True:
        code = input("Code (or r to resend, q to quit): ").strip().lower()
        if code == "q":
            return 1
        if code == "r":
            print("✓ Sent a new code." if dupr_live.resend_code(challenge) else "Resend failed; run the script again.")
            continue
        if not (code.isdigit() and len(code) == 6):
            print("Enter the 6 digits from the email.")
            continue
        res = dupr_live.verify_code(challenge, code) or {}
        if res.get("token"):
            save(res["token"])
            print(f"✓ Signed in. Token saved to {CONFIG} (good for about 30 days).")
            return 0
        print(f"✗ {res.get('error', 'DUPR did not accept that code')}")


if __name__ == "__main__":
    sys.exit(main())
