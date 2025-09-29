#!/usr/bin/env python3
"""
Search for specific players in the DUPR database
"""
from sqlalchemy.orm import Session
from dupr_db import open_db, Player, Rating
from sqlalchemy import select, or_, and_

def search_players():
    """Search for the specific players from the CSV data"""
    
    # Open database connection
    engine = open_db()
    
    # Players to search for
    players_to_find = [
        {
            "first_name": "Sarah",
            "last_name": "Tripp", 
            "email": "sarahtripp.1014@gmail.com",
            "phone": "330-224-2952"
        },
        {
            "first_name": "Matt",
            "last_name": "Deaver",
            "email": "thedinkingdeaver@gmail.com", 
            "phone": "409-679-0393"
        },
        {
            "first_name": "Chih-Ming",
            "last_name": "Chiang",
            "email": "jc10167416@yahoo.com",
            "phone": "303-587-8634"
        },
        {
            "first_name": "Gary",
            "last_name": "Bata",
            "email": "gabata72@gmail.com",
            "phone": "720-341-7448"
        }
    ]
    
    with Session(engine) as session:
        print("Searching for players in DUPR database...")
        print("=" * 60)
        
        for player_info in players_to_find:
            print(f"\nSearching for: {player_info['first_name']} {player_info['last_name']}")
            print(f"Email: {player_info['email']}")
            print(f"Phone: {player_info['phone']}")
            print("-" * 40)
            
            # Search by email first
            email_results = session.execute(
                select(Player).where(Player.email == player_info['email'])
            ).scalars().all()
            
            if email_results:
                print(f"✓ Found {len(email_results)} player(s) by email:")
                for player in email_results:
                    print(f"  - DUPR ID: {player.dupr_id}")
                    print(f"  - Full Name: {player.full_name}")
                    print(f"  - First Name: {player.first_name}")
                    print(f"  - Last Name: {player.last_name}")
                    print(f"  - Gender: {player.gender}")
                    print(f"  - Age: {player.age}")
                    print(f"  - Phone: {player.phone}")
                    print(f"  - Doubles Rating: {player.rating.doubles_rating()}")
                    print(f"  - Singles Rating: {player.rating.singles_rating()}")
                    print(f"  - Image URL: {player.image_url}")
            else:
                print("✗ No players found by email")
                
                # Try searching by name
                name_results = session.execute(
                    select(Player).where(
                        and_(
                            or_(Player.first_name.ilike(f"%{player_info['first_name']}%"),
                                Player.full_name.ilike(f"%{player_info['first_name']}%")),
                            or_(Player.last_name.ilike(f"%{player_info['last_name']}%"),
                                Player.full_name.ilike(f"%{player_info['last_name']}%"))
                        )
                    )
                ).scalars().all()
                
                if name_results:
                    print(f"✓ Found {len(name_results)} player(s) by name:")
                    for player in name_results:
                        print(f"  - DUPR ID: {player.dupr_id}")
                        print(f"  - Full Name: {player.full_name}")
                        print(f"  - First Name: {player.first_name}")
                        print(f"  - Last Name: {player.last_name}")
                        print(f"  - Email: {player.email}")
                        print(f"  - Phone: {player.phone}")
                        print(f"  - Doubles Rating: {player.rating.doubles_rating()}")
                        print(f"  - Singles Rating: {player.rating.singles_rating()}")
                else:
                    print("✗ No players found by name either")
            
            print()

if __name__ == "__main__":
    search_players()
