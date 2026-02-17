#!/usr/bin/env python3
"""
Crawl all club members' match history and store club matches in the local DB.
Used to collect data for reverse-engineering the DUPR rating algorithm.

Run from repo root with .env set (DUPR_USERNAME, DUPR_PASSWORD, DUPR_CLUB_ID).
Usage: python scripts/crawl_club_matches.py [--limit N] [--delay SEC]
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from dupr_client import DuprClient
from dupr_db import open_db, ClubMatchRaw
from sqlalchemy.orm import Session
from sqlalchemy import select

def main():
    parser = argparse.ArgumentParser(description="Crawl club match history into local DB")
    parser.add_argument("--limit", type=int, default=0, help="Max members to process (0 = all)")
    parser.add_argument("--max-matches", type=int, default=0, help="Stop after storing this many club matches (0 = no limit)")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between member API calls (seconds)")
    args = parser.parse_args()

    club_id = os.getenv("DUPR_CLUB_ID")
    if not club_id:
        print("Error: DUPR_CLUB_ID must be set in .env")
        sys.exit(1)
    club_id = int(club_id)

    username = os.getenv("DUPR_USERNAME")
    password = os.getenv("DUPR_PASSWORD")
    if not username or not password:
        print("Error: DUPR_USERNAME and DUPR_PASSWORD must be set in .env")
        sys.exit(1)

    print("Authenticating...")
    dupr = DuprClient(verbose=False)
    dupr.auth_user(username, password)

    print(f"Fetching club members (club_id={club_id})...")
    rc, members = dupr.get_members_by_club(str(club_id), sort_by_rating=True)
    if rc != 200:
        print(f"Failed to get members: {rc}")
        sys.exit(1)

    member_ids = []
    for m in members:
        pid = m.get("id") or m.get("duprId")
        if pid is not None:
            member_ids.append(str(pid))
    print(f"Found {len(member_ids)} members")

    if args.limit > 0:
        member_ids = member_ids[: args.limit]
        print(f"Limiting to first {args.limit} members")

    eng = open_db()
    
    # Load all existing match_ids from DB upfront (fast lookup, no duplicate checks needed)
    print("Loading existing match IDs from DB...")
    existing_match_ids = set()
    with Session(eng) as sess:
        result = sess.execute(select(ClubMatchRaw.match_id))
        existing_match_ids = {r[0] for r in result}
    print(f"Found {len(existing_match_ids)} existing matches in DB")
    
    seen_match_ids = set()
    new_matches = 0
    total_matches_fetched = 0

    for i, mid in enumerate(member_ids, 1):
        if i % 50 == 0:
            print(f"Progress: {i}/{len(member_ids)} members, {new_matches} new club matches stored so far")
        rc, matches = dupr.get_member_match_history_p(mid)
        if rc != 200:
            continue
        total_matches_fetched += len(matches)
        for m in matches:
            match_id = m.get("matchId") or m.get("id")
            if not match_id:
                continue
            # Only store matches that belong to our club
            m_club = m.get("clubId")
            if m_club is None:
                continue
            if int(m_club) != club_id:
                continue
            # Skip if already seen in this run or already in DB
            if match_id in seen_match_ids or match_id in existing_match_ids:
                continue
            seen_match_ids.add(match_id)
            event_date = m.get("eventDate", "")
            raw_json = json.dumps(m)
            with Session(eng) as sess:
                row = ClubMatchRaw(
                    match_id=match_id,
                    club_id=club_id,
                    event_date=event_date,
                    raw_json=raw_json,
                )
                sess.add(row)
                sess.commit()
                new_matches += 1
                if args.max_matches > 0 and new_matches >= args.max_matches:
                    print(f"Reached --max-matches={args.max_matches}, stopping.")
                    break
        if args.max_matches > 0 and new_matches >= args.max_matches:
            break
        time.sleep(args.delay)

    print(f"Done. Fetched {total_matches_fetched} total match records.")
    print(f"Stored {new_matches} new club matches. Total unique club matches: {len(seen_match_ids)}")

if __name__ == "__main__":
    main()
