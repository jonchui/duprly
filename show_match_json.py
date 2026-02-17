#!/usr/bin/env python3
"""Show raw match JSON data to inspect rating change fields"""

import json
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dupr_client import DuprClient
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    # Your DUPR ID
    dupr_id = "4405492894"  # Numeric ID
    
    print("Connecting to DUPR API...")
    dupr = DuprClient(verbose=False)
    
    print(f"Fetching match history for {dupr_id}...")
    rc, matches = dupr.get_member_match_history_p(dupr_id)
    
    if rc == 200 and matches:
        print(f"\n✓ Found {len(matches)} matches\n")
        print("="*80)
        print("RAW JSON DATA - First Match (most recent):")
        print("="*80)
        print(json.dumps(matches[0], indent=2))
        
        if len(matches) > 1:
            print("\n" + "="*80)
            print("RAW JSON DATA - Second Match:")
            print("="*80)
            print(json.dumps(matches[1], indent=2))
        
        if len(matches) > 2:
            print("\n" + "="*80)
            print("RAW JSON DATA - Third Match:")
            print("="*80)
            print(json.dumps(matches[2], indent=2))
        
        print("\n" + "="*80)
        print("KEY FIELDS TO CHECK:")
        print("="*80)
        print("Look for fields like:")
        print("  - ratingChange, ratingDelta, ratingBefore, ratingAfter")
        print("  - preRating, postRating, doublesRatingChange")
        print("  - In teams[].player1/player2: rating, ratingChange, etc.")
        print("="*80)
    else:
        print(f"✗ Failed: status {rc}")
        if matches:
            print(f"Response: {matches}")
        sys.exit(1)
