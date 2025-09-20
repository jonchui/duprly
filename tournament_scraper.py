#!/usr/bin/env python3
"""
Tournament Pool Scraper for DUPR Analysis
Scrapes player names from tournament brackets and looks up their DUPR ratings
"""

import requests
from bs4 import BeautifulSoup
import time
import re
from dupr_db import open_db, Player, Rating
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from dupr_client import DuprClient
import os
from dotenv import load_dotenv

load_dotenv()

def scrape_tournament_pool(url):
    """Scrape player names from tournament pool page"""
    print(f"Scraping tournament pool: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for player names in various possible containers
        player_names = set()
        
        # Try different selectors that might contain player names
        selectors = [
            '.player-name',
            '.participant-name', 
            '.bracket-player',
            '.pool-player',
            '[class*="player"]',
            '[class*="participant"]',
            '.name',
            'td',
            'span'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                # Look for names (2+ words, not just numbers or single letters)
                if len(text) > 3 and re.match(r'^[A-Za-z\s\.]+$', text) and ' ' in text:
                    # Clean up the name
                    name = ' '.join(text.split())  # Remove extra whitespace
                    if len(name.split()) >= 2:  # At least first and last name
                        player_names.add(name)
        
        # Also try to find names in table cells
        tables = soup.find_all('table')
        for table in tables:
            cells = table.find_all(['td', 'th'])
            for cell in cells:
                text = cell.get_text(strip=True)
                if len(text) > 3 and re.match(r'^[A-Za-z\s\.]+$', text) and ' ' in text:
                    name = ' '.join(text.split())
                    if len(name.split()) >= 2:
                        player_names.add(name)
        
        print(f"Found {len(player_names)} potential player names:")
        for name in sorted(player_names):
            print(f"  - {name}")
            
        return list(player_names)
        
    except Exception as e:
        print(f"Error scraping tournament: {e}")
        return []

def find_player_in_db(name, sess):
    """Find player in our database by name"""
    # Try exact match first
    player = sess.execute(
        select(Player).where(Player.full_name == name)
    ).scalar_one_or_none()
    
    if player:
        return player
    
    # Try case-insensitive match
    player = sess.execute(
        select(Player).where(Player.full_name.ilike(name))
    ).scalar_one_or_none()
    
    if player:
        return player
    
    # Try partial matches (first name + last name)
    name_parts = name.split()
    if len(name_parts) >= 2:
        first_name = name_parts[0]
        last_name = name_parts[-1]
        
        player = sess.execute(
            select(Player).where(
                or_(
                    Player.first_name.ilike(f'%{first_name}%'),
                    Player.last_name.ilike(f'%{last_name}%')
                )
            )
        ).scalar_one_or_none()
        
        if player:
            return player
    
    return None

def get_player_dupr_rating(player, dupr_client):
    """Get player's DUPR rating from DUPR API"""
    try:
        rc, pdata = dupr_client.get_player(player.dupr_id)
        if rc == 200 and pdata:
            # Extract rating from the response
            doubles_rating = pdata.get('doubles')
            singles_rating = pdata.get('singles')
            return doubles_rating, singles_rating
    except Exception as e:
        print(f"Error getting DUPR rating for {player.full_name}: {e}")
    
    return None, None

def analyze_tournament_pool(tournament_url):
    """Main function to scrape and analyze tournament pool"""
    print("🏆 Tournament Pool Analysis")
    print("=" * 50)
    
    # Scrape player names
    player_names = scrape_tournament_pool(tournament_url)
    
    if not player_names:
        print("❌ No player names found. Check the URL or try a different approach.")
        return
    
    # Connect to database
    eng = open_db()
    dupr_client = DuprClient()
    
    # Authenticate with DUPR
    username = os.getenv("DUPR_USERNAME")
    password = os.getenv("DUPR_PASSWORD")
    if username and password:
        dupr_client.auth_user(username, password)
        print("✅ Authenticated with DUPR")
    else:
        print("⚠️  No DUPR credentials found, will only use local database")
    
    with Session(eng) as sess:
        found_players = []
        missing_players = []
        
        print(f"\n🔍 Looking up {len(player_names)} players...")
        
        for name in player_names:
            print(f"\nLooking up: {name}")
            
            # Try to find in our database first
            player = find_player_in_db(name, sess)
            
            if player:
                print(f"  ✅ Found in database: {player.full_name} (DUPR ID: {player.dupr_id})")
                
                # Get current rating
                if player.rating:
                    doubles = player.rating.doubles
                    singles = player.rating.singles
                    print(f"  📊 Local rating - Doubles: {doubles}, Singles: {singles}")
                else:
                    print(f"  ⚠️  No local rating data")
                
                # Try to get fresh rating from DUPR
                if username and password:
                    doubles_rating, singles_rating = get_player_dupr_rating(player, dupr_client)
                    if doubles_rating:
                        print(f"  🔄 Fresh DUPR rating - Doubles: {doubles_rating}, Singles: {singles_rating}")
                
                found_players.append({
                    'name': player.full_name,
                    'dupr_id': player.dupr_id,
                    'doubles_rating': player.rating.doubles if player.rating else None,
                    'singles_rating': player.rating.singles if player.rating else None
                })
            else:
                print(f"  ❌ Not found in database")
                missing_players.append(name)
        
        # Summary
        print(f"\n📊 Tournament Pool Analysis Summary")
        print("=" * 50)
        print(f"Total players in pool: {len(player_names)}")
        print(f"Found in database: {len(found_players)}")
        print(f"Missing from database: {len(missing_players)}")
        
        if found_players:
            print(f"\n✅ Players with ratings:")
            for player in found_players:
                rating_str = f"Doubles: {player['doubles_rating']}" if player['doubles_rating'] else "No rating"
                print(f"  {player['name']} - {rating_str}")
        
        if missing_players:
            print(f"\n❌ Players not found:")
            for name in missing_players:
                print(f"  {name}")
        
        # Calculate average rating if we have enough data
        valid_ratings = [p['doubles_rating'] for p in found_players if p['doubles_rating'] is not None]
        if valid_ratings:
            avg_rating = sum(valid_ratings) / len(valid_ratings)
            print(f"\n📈 Pool Statistics:")
            print(f"  Average doubles rating: {avg_rating:.2f}")
            print(f"  Players with ratings: {len(valid_ratings)}/{len(found_players)}")
            
            # Find your rating for comparison
            your_player = next((p for p in found_players if 'Jon chui' in p['name'] or 'Jon' in p['name']), None)
            if your_player and your_player['doubles_rating']:
                your_rating = your_player['doubles_rating']
                print(f"  Your rating: {your_rating}")
                if your_rating > avg_rating:
                    print(f"  🎯 You're above average by {your_rating - avg_rating:.2f} points!")
                else:
                    print(f"  📈 Pool average is {avg_rating - your_rating:.2f} points above you")

if __name__ == "__main__":
    tournament_url = "https://brackets.pickleballtournaments.com/tournaments/fall-into-life-time-location-changed-to-centennial/events/65DD1C59-8F4F-4D57-AC25-F19BEDA5F43D/pools/4485A7BA-53DA-4D79-A73B-887770514C17"
    analyze_tournament_pool(tournament_url)
