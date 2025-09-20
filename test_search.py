#!/usr/bin/env python3

import os
from dotenv import load_dotenv
from dupr_client import DuprClient

load_dotenv()

def test_search():
    dupr = DuprClient()
    
    # Authenticate
    username = os.getenv("DUPR_USERNAME")
    password = os.getenv("DUPR_PASSWORD")
    dupr.auth_user(username, password)
    
    # Test search
    print("🔍 Testing DUPR search API...")
    print("=" * 50)
    
    # Search for Kirk White
    rc, results = dupr.search_players("Kirk White")
    
    if rc == 200 and results:
        hits = results.get('hits', [])
        total = results.get('total', 0)
        
        print(f"Found {total} players matching 'Kirk White':")
        print()
        
        for i, player in enumerate(hits, 1):
            name = player.get('fullName', 'Unknown')
            dupr_id = player.get('duprId', 'Unknown')
            age = player.get('age', 'Unknown')
            location = player.get('shortAddress', 'Unknown')
            distance = player.get('distance', 'Unknown')
            
            ratings = player.get('ratings', {})
            doubles = ratings.get('doubles', 'NR')
            singles = ratings.get('singles', 'NR')
            
            print(f"{i:2d}. {name}")
            print(f"    DUPR ID: {dupr_id}")
            print(f"    Age: {age}, Location: {location}")
            print(f"    Distance: {distance}")
            print(f"    Doubles: {doubles}, Singles: {singles}")
            print()
    else:
        print(f"❌ Search failed or no results found")
        print(f"   Status code: {rc}")

if __name__ == "__main__":
    test_search()
