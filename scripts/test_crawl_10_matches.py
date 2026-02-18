#!/usr/bin/env python3
"""
Test script: Crawl 10 matches and check if reliability is in the fresh match data.
This helps determine if reliability is available at match time in the API response.
"""

import os
import sys
import json
import time
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from dupr_client import DuprClient
# from dupr_db import open_db, ClubMatchRaw
# from sqlalchemy.orm import Session
# from sqlalchemy import select

def deep_search_reliability(obj, path="", found_keys=None, max_depth=4, depth=0):
    """Recursively search for reliability-related keys"""
    if found_keys is None:
        found_keys = []
    if depth > max_depth:
        return found_keys
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = f"{path}.{key}" if path else key
            if 'reliab' in key.lower() or 'verif' in key.lower():
                found_keys.append((current_path, value, type(value).__name__))
            if isinstance(value, (dict, list)):
                deep_search_reliability(value, current_path, found_keys, max_depth, depth + 1)
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:2]):  # Check first 2 items
            deep_search_reliability(item, f"{path}[{i}]", found_keys, max_depth, depth + 1)
    
    return found_keys

def inspect_match_json(match_json, match_id):
    """Inspect match JSON to find reliability fields"""
    print(f"\n{'='*80}")
    print(f"Match ID: {match_id}")
    print(f"{'='*80}")
    
    try:
        data = match_json if isinstance(match_json, dict) else json.loads(match_json)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return
    
    # Deep search for reliability
    print("\n🔍 DEEP SEARCH for reliability-related keys...")
    found = deep_search_reliability(data)
    
    if found:
        print(f"\n⭐ FOUND {len(found)} RELIABILITY-RELATED KEYS:")
        for path, value, vtype in found:
            print(f"  {path} = {value} (type: {vtype})")
    else:
        print("\n❌ NO reliability-related keys found in entire JSON structure")
    
    # Also show preMatchRatingAndImpact structure
    teams = data.get("teams", [])
    if teams and len(teams) >= 1:
        pre = teams[0].get("preMatchRatingAndImpact")
        if pre:
            print(f"\n📋 Full preMatchRatingAndImpact JSON:")
            print(json.dumps(pre, indent=2))

def main():
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

    # Limit to first few members
    member_ids = member_ids[:5]  # Check first 5 members
    print(f"Checking first {len(member_ids)} members for matches...")

    # eng = open_db()
    # existing_match_ids = set()
    # with Session(eng) as sess:
    #     result = sess.execute(select(ClubMatchRaw.match_id))
    #     existing_match_ids = {r[0] for r in result}
    # print(f"Found {len(existing_match_ids)} existing matches in DB")
    existing_match_ids = set()  # Skip DB for now
    
    seen_match_ids = set()
    new_matches = 0
    matches_to_inspect = []

    print(f"\n{'='*80}")
    print("CRAWLING MATCHES (limit: 10)")
    print(f"{'='*80}")

    for i, mid in enumerate(member_ids, 1):
        if new_matches >= 10:
            break
        print(f"\nProcessing member {i}/{len(member_ids)} (ID: {mid})...")
        rc, matches = dupr.get_member_match_history_p(mid)
        if rc != 200:
            print(f"  ⚠️  Failed to get matches: {rc}")
            continue
        
        print(f"  Found {len(matches)} matches in history")
        
        for m in matches:
            if new_matches >= 10:
                break
            match_id = m.get("matchId") or m.get("id")
            if not match_id:
                continue
            # Only store matches that belong to our club
            m_club = m.get("clubId")
            if m_club is None:
                continue
            if int(m_club) != club_id:
                continue
            # Skip if already seen
            if match_id in seen_match_ids:
                continue
            
            seen_match_ids.add(match_id)
            new_matches += 1
            matches_to_inspect.append((match_id, m))
            print(f"  ✓ Found match {match_id} ({new_matches}/10)")
        
        time.sleep(0.2)

    print(f"\n{'='*80}")
    print(f"Crawled {new_matches} new matches")
    print(f"{'='*80}")

    # Inspect matches for reliability
    print(f"\n{'='*80}")
    print("INSPECTING MATCHES FOR RELIABILITY DATA")
    print(f"{'='*80}")
    
    for match_id, match_data in matches_to_inspect[:5]:  # Inspect first 5
        inspect_match_json(match_data, match_id)
    
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total matches crawled: {new_matches}")
    print(f"\nNext steps:")
    print(f"1. Run: python scripts/extract_match_rating_data_with_reliability.py")
    print(f"2. Check if reliability was found in the extracted CSV")
    print(f"3. If found, we can use it for model fitting!")

if __name__ == "__main__":
    main()
