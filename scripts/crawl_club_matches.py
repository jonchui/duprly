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

def get_player_ids_from_match(match_data):
    """Extract player IDs from match data"""
    teams = match_data.get("teams", [])
    if len(teams) != 2:
        return None
    
    player_ids = []
    for team in teams:
        p1 = team.get("player1", {})
        p2 = team.get("player2", {})
        p1_id = p1.get("id") or p1.get("duprId")
        p2_id = p2.get("id") or p2.get("duprId")
        if p1_id and p2_id:
            player_ids.extend([str(p1_id), str(p2_id)])
        else:
            return None
    
    return player_ids if len(player_ids) == 4 else None

def get_reliability_from_player(player_data):
    """Extract reliability from player data"""
    if not player_data:
        return None
    
    ratings = player_data.get("ratings", {})
    if isinstance(ratings, dict):
        rel = (ratings.get("doublesReliabilityScore") or 
               ratings.get("doublesVerified") or
               ratings.get("reliability"))
    else:
        rel = None
    
    if rel is None:
        rel = (player_data.get("doublesReliabilityScore") or 
               player_data.get("doublesVerified") or
               player_data.get("reliability"))
    
    if rel is not None:
        try:
            return int(rel)
        except (ValueError, TypeError):
            pass
    return None

def enrich_match_with_reliability(match_data, dupr_client):
    """Fetch reliability for all players and add to match data"""
    player_ids = get_player_ids_from_match(match_data)
    if not player_ids:
        return match_data
    
    reliabilities = []
    for pid in player_ids:
        try:
            rc, player_data = dupr_client.get_player(pid)
            if rc == 200 and player_data:
                rel = get_reliability_from_player(player_data)
                reliabilities.append(rel)
            else:
                reliabilities.append(None)
            time.sleep(0.05)  # Small delay to avoid rate limits
        except Exception as e:
            reliabilities.append(None)
    
    # Add reliability to match data as metadata
    if not match_data.get("_crawl_metadata"):
        match_data["_crawl_metadata"] = {}
    
    match_data["_crawl_metadata"]["reliability"] = {
        "player1": reliabilities[0],
        "player2": reliabilities[1],
        "player3": reliabilities[2],
        "player4": reliabilities[3],
        "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return match_data

def main():
    parser = argparse.ArgumentParser(description="Crawl club match history into local DB")
    parser.add_argument("--limit", type=int, default=0, help="Max members to process (0 = all)")
    parser.add_argument("--max-matches", type=int, default=0, help="Stop after storing this many club matches (0 = no limit)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between member API calls (seconds); increase if you see 429 rate limits")
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
    batch_size = 50
    batch = []
    batch_num = 0
    reliability_fetched = 0

    print(f"\n[001] Starting crawl with batch size: {batch_size}")
    print(f"[002] Target: {args.max_matches if args.max_matches > 0 else 'all'} matches")
    print(f"[003] Processing {len(member_ids)} members\n")

    for i, mid in enumerate(member_ids, 1):
        if i % 50 == 0:
            print(f"[{i:03d}] Progress: {i}/{len(member_ids)} members, {new_matches} matches stored, {reliability_fetched} with reliability")
        
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
            
            # Enrich with reliability at crawl time
            try:
                enriched_match = enrich_match_with_reliability(m, dupr)
                rel_data = enriched_match.get("_crawl_metadata", {}).get("reliability", {})
                if all(rel_data.get(f"player{i}") is not None for i in range(1,5)):
                    reliability_fetched += 1
            except Exception as e:
                print(f"[ERR] Failed to fetch reliability for match {match_id}: {e}")
                enriched_match = m
            
            event_date = enriched_match.get("eventDate", "")
            raw_json = json.dumps(enriched_match)
            
            batch.append({
                'match_id': match_id,
                'club_id': club_id,
                'event_date': event_date,
                'raw_json': raw_json
            })
            
            # Commit batch when it reaches batch_size
            if len(batch) >= batch_size:
                batch_num += 1
                print(f"[BATCH {batch_num:03d}] Committing batch of {len(batch)} matches...")
                with Session(eng) as sess:
                    for item in batch:
                        row = ClubMatchRaw(
                            match_id=item['match_id'],
                            club_id=item['club_id'],
                            event_date=item['event_date'],
                            raw_json=item['raw_json'],
                        )
                        sess.add(row)
                    sess.commit()
                print(f"[BATCH {batch_num:03d}] ✓ Committed {len(batch)} matches (total stored: {new_matches + len(batch)})")
                new_matches += len(batch)
                batch = []
            
            if args.max_matches > 0 and new_matches >= args.max_matches:
                print(f"[STOP] Reached --max-matches={args.max_matches}, stopping.")
                break
        
        if args.max_matches > 0 and new_matches >= args.max_matches:
            break
        time.sleep(args.delay)
    
    # Commit remaining batch
    if batch:
        batch_num += 1
        print(f"\n[BATCH {batch_num:03d}] Committing final batch of {len(batch)} matches...")
        with Session(eng) as sess:
            for item in batch:
                row = ClubMatchRaw(
                    match_id=item['match_id'],
                    club_id=item['club_id'],
                    event_date=item['event_date'],
                    raw_json=item['raw_json'],
                )
                sess.add(row)
            sess.commit()
        print(f"[BATCH {batch_num:03d}] ✓ Committed {len(batch)} matches")
        new_matches += len(batch)

    print(f"\n[FINISH] Crawl complete!")
    print(f"[STATS] Fetched {total_matches_fetched} total match records")
    print(f"[STATS] Stored {new_matches} new club matches")
    print(f"[STATS] Matches with reliability: {reliability_fetched}/{new_matches}")
    print(f"[STATS] Total unique club matches: {len(seen_match_ids)}")

if __name__ == "__main__":
    main()
