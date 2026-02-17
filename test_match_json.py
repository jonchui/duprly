#!/usr/bin/env python3
"""Test script to show raw match JSON data for rating changes"""

import json
import sys
from dupr_client import DuprClient
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    # Your DUPR ID from earlier
    dupr_id = "4405492894"  # or "0YVNWN"
    
    dupr = DuprClient(verbose=False)
    rc, matches = dupr.get_member_match_history_p(dupr_id)
    
    if rc == 200 and matches:
        print(f"Found {len(matches)} matches\n")
        print("=" * 80)
        print("RAW JSON DATA - First 3 matches:")
        print("=" * 80)
        
        for i, match in enumerate(matches[:3], 1):
            print(f"\n{'='*80}")
            print(f"MATCH {i}")
            print(f"{'='*80}")
            print(json.dumps(match, indent=2))
            print()
    else:
        print(f"Failed: status {rc}")
        sys.exit(1)
