#!/usr/bin/env python3
"""Inspect raw club member API response to see rating structure and count members with ratings.
Run from repo root: python3 scripts/inspect_club_members.py
Writes first member JSON to club_member_sample.json for debugging."""
import os
import sys
import json

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)

from dotenv import load_dotenv
load_dotenv()

from duprly_secrets import get_secret
from dupr_client import DuprClient

def main():
    club_id = get_secret("DUPR_CLUB_ID")
    if not club_id:
        print("DUPR_CLUB_ID not set in .env or keychain")
        sys.exit(1)
    username = get_secret("DUPR_USERNAME")
    password = get_secret("DUPR_PASSWORD")
    if not username or not password:
        print("DUPR_USERNAME/DUPR_PASSWORD not set")
        sys.exit(1)

    d = DuprClient()
    d.auth_user(username, password)
    rc, members = d.get_members_by_club(club_id)
    if rc != 200:
        print(f"API returned {rc}")
        sys.exit(1)

    print(f"Total members: {len(members)}\n")

    if members:
        print("Keys on first member:", list(members[0].keys()))
        out_path = os.path.join(REPO_ROOT, "club_member_sample.json")
        with open(out_path, "w") as f:
            json.dump(members[0], f, indent=2, default=str)
        print(f"First member JSON written to: {out_path}\n")

    with_doubles = sum(1 for m in members if d._member_rating_value(m, "doubles") != "NR")
    with_singles = sum(1 for m in members if d._member_rating_value(m, "singles") != "NR")
    print("--- Counts (using all key paths) ---")
    print(f"Members with doubles rating (non-NR): {with_doubles}")
    print(f"Members with singles rating (non-NR): {with_singles}")

    if with_doubles == 0 and members:
        print("\nNo ratings found with current key paths. Check club_member_sample.json for actual API structure.")

if __name__ == "__main__":
    main()
