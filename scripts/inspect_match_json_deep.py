#!/usr/bin/env python3
"""
Deep inspection of match JSON to find ALL possible reliability fields.
This will print the full JSON structure so we can see everything.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dupr_db import open_db, ClubMatchRaw
from sqlalchemy import select

def deep_inspect_json(obj, path="", max_depth=5, current_depth=0):
    """Recursively inspect JSON to find all keys"""
    if current_depth > max_depth:
        return
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = f"{path}.{key}" if path else key
            # Check if this key might be related to reliability
            if 'reliab' in key.lower() or 'verif' in key.lower():
                print(f"⭐ FOUND RELIABILITY KEY: {current_path} = {value} (type: {type(value).__name__})")
            # Recurse into nested structures
            if isinstance(value, (dict, list)):
                deep_inspect_json(value, current_path, max_depth, current_depth + 1)
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:3]):  # Only check first 3 items
            deep_inspect_json(item, f"{path}[{i}]", max_depth, current_depth + 1)

def main():
    eng = open_db()
    
    print("="*80)
    print("DEEP INSPECTION: Looking for reliability in match JSON")
    print("="*80)
    
    with eng.connect() as conn:
        result = conn.execute(select(ClubMatchRaw).limit(3))
        for i, r in enumerate(result, 1):
            print(f"\n{'='*80}")
            print(f"MATCH {i}: {r.match_id}")
            print(f"{'='*80}")
            
            try:
                data = json.loads(r.raw_json)
                
                # First, do a deep search for reliability-related keys
                print("\n🔍 Searching for reliability-related keys...")
                deep_inspect_json(data)
                
                # Also print the full structure of preMatchRatingAndImpact
                print("\n📋 Full preMatchRatingAndImpact structure:")
                teams = data.get("teams", [])
                if teams and len(teams) >= 1:
                    pre = teams[0].get("preMatchRatingAndImpact")
                    if pre:
                        print(json.dumps(pre, indent=2))
                    else:
                        print("  No preMatchRatingAndImpact found")
                
                # Print player1/player2 structure
                print("\n📋 Full player1 structure:")
                if teams and len(teams) >= 1:
                    player1 = teams[0].get("player1")
                    if player1:
                        print(json.dumps(player1, indent=2))
                    else:
                        print("  No player1 found")
                
            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("If reliability keys were found above (⭐), they exist in the JSON!")
    print("If not, reliability is NOT in the match JSON and must be fetched separately.")

if __name__ == "__main__":
    main()
