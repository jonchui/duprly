#!/usr/bin/env python3
"""
Add reliability data to match_rating_data.csv by fetching from club_match_raw JSON
or from DUPR API if needed.
"""

import json
import csv
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dupr_db import open_db, ClubMatchRaw
from sqlalchemy import select
from dupr_client import DuprClient
from dotenv import load_dotenv

load_dotenv()

def get_player_ids_from_match_json(match_json):
    """Extract player IDs from match JSON"""
    try:
        data = json.loads(match_json) if isinstance(match_json, str) else match_json
        teams = data.get("teams", [])
        if len(teams) != 2:
            return None
        
        player_ids = []
        for team in teams:
            players = team.get("players", [])
            if len(players) >= 2:
                p1_id = players[0].get("id") or players[0].get("duprId")
                p2_id = players[1].get("id") or players[1].get("duprId")
                player_ids.extend([p1_id, p2_id])
            else:
                return None
        
        if len(player_ids) == 4 and all(p is not None for p in player_ids):
            return player_ids
    except Exception as e:
        print(f"Error parsing match JSON: {e}")
    return None

def get_reliability_from_player_data(player_data):
    """Extract reliability from player data"""
    if not player_data:
        return None
    
    # Try different possible field names
    rel = (player_data.get("doublesReliabilityScore") or 
           player_data.get("doublesVerified") or
           player_data.get("reliability") or
           player_data.get("doublesReliability"))
    
    if rel is not None:
        try:
            return int(rel)
        except (ValueError, TypeError):
            pass
    return None

def main():
    csv_path = Path(__file__).resolve().parent.parent / "match_rating_data.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} not found!")
        sys.exit(1)
    
    # Load existing CSV
    matches = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            matches.append(row)
    
    print(f"Loaded {len(matches)} matches from CSV")
    
    # Create match_id -> row mapping
    match_dict = {row['match_id']: row for row in matches}
    
    # Try to get reliability from database first
    print("\nFetching reliability from database...")
    eng = open_db()
    reliability_found = 0
    
    dupr_client = None
    try:
        dupr_client = DuprClient(verbose=False)
        username = os.getenv("DUPR_USERNAME")
        password = os.getenv("DUPR_PASSWORD")
        if username and password:
            dupr_client.auth_user(username, password)
            print("Authenticated with DUPR API")
    except Exception as e:
        print(f"Warning: Could not authenticate with DUPR API: {e}")
        print("Will only use database data")
    
    with eng.connect() as conn:
        result = conn.execute(select(ClubMatchRaw))
        for r in result:
            match_id = str(r.match_id)
            if match_id not in match_dict:
                continue
            
            # Try to get player IDs from JSON
            player_ids = get_player_ids_from_match_json(r.raw_json)
            if not player_ids:
                continue
            
            # Try to get reliability from JSON first
            try:
                data = json.loads(r.raw_json) if isinstance(r.raw_json, str) else r.raw_json
                teams = data.get("teams", [])
                rels = [None, None, None, None]
                
                # Check if reliability is in the JSON
                for i, team in enumerate(teams):
                    players = team.get("players", [])
                    if len(players) >= 2:
                        rel1 = get_reliability_from_player_data(players[0])
                        rel2 = get_reliability_from_player_data(players[1])
                        if i == 0:
                            rels[0], rels[1] = rel1, rel2
                        else:
                            rels[2], rels[3] = rel1, rel2
                
                # If we got all 4 reliabilities, use them
                if all(r is not None for r in rels):
                    match_dict[match_id]['rel1'] = rels[0]
                    match_dict[match_id]['rel2'] = rels[1]
                    match_dict[match_id]['rel3'] = rels[2]
                    match_dict[match_id]['rel4'] = rels[3]
                    reliability_found += 1
                    continue
            except Exception:
                pass
            
            # If not in JSON, try fetching from API
            if dupr_client:
                try:
                    rels = []
                    for pid in player_ids:
                        rc, player_data = dupr_client.get_player(str(pid))
                        if rc == 200 and player_data:
                            rel = get_reliability_from_player_data(player_data)
                            rels.append(rel)
                        else:
                            rels.append(None)
                    
                    if all(r is not None for r in rels):
                        match_dict[match_id]['rel1'] = rels[0]
                        match_dict[match_id]['rel2'] = rels[1]
                        match_dict[match_id]['rel3'] = rels[2]
                        match_dict[match_id]['rel4'] = rels[3]
                        reliability_found += 1
                except Exception as e:
                    if reliability_found < 5:  # Only print first few errors
                        print(f"  Error fetching reliability for match {match_id}: {e}")
    
    print(f"\nFound reliability for {reliability_found} matches")
    
    # Write updated CSV
    if reliability_found > 0:
        # Check if rel1 column exists
        fieldnames = list(matches[0].keys())
        if 'rel1' not in fieldnames:
            fieldnames.extend(['rel1', 'rel2', 'rel3', 'rel4'])
        
        output_path = csv_path.parent / "match_rating_data_with_reliability.csv"
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in matches:
                # Ensure all reliability fields exist
                for i in range(1, 5):
                    key = f'rel{i}'
                    if key not in row:
                        row[key] = ''
                writer.writerow(row)
        
        print(f"Wrote updated CSV to {output_path}")
        print(f"Use this file for validation with reliability")
    else:
        print("\nNo reliability data found. You may need to:")
        print("1. Check if player data includes reliability in club_match_raw")
        print("2. Ensure DUPR API credentials are set in .env")
        print("3. Run with API access to fetch reliability")

if __name__ == "__main__":
    main()
