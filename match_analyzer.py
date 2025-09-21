#!/usr/bin/env python3

import json
import os
from dotenv import load_dotenv
from dupr_client import DuprClient

load_dotenv()

def analyze_matches(match_file: str):
    """Analyze matches from a file and show expected scores and rating targets"""
    
    dupr = DuprClient()
    dupr.auth_user(os.getenv('DUPR_USERNAME'), os.getenv('DUPR_PASSWORD'))
    
    # Load match data
    try:
        with open(match_file, 'r') as f:
            data = json.load(f)
        matches = data.get('matches', [])
    except FileNotFoundError:
        print(f"❌ File {match_file} not found")
        return
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in {match_file}")
        return
    
    print('🏆 MATCH ANALYSIS & RATING IMPROVEMENT TARGETS')
    print('=' * 80)
    
    # Player database
    player_db = {
        'Jonathan Chui': {'dupr_id': '0YVNWN', 'rating': 3.734},
        'Kirk White': {'dupr_id': '3Y5YG3', 'rating': 4.642},
        'Milos Koprivica': {'dupr_id': 'Q5440D', 'rating': 4.163},
        'Robert Kuseski': {'dupr_id': 'M2WJVO', 'rating': 4.100},
        'Thomas Noonan': {'dupr_id': 'N7XNVW', 'rating': 4.151},
        'Michael Fox': {'dupr_id': 'RZVG0E', 'rating': 4.625},
        'Leo Alvarez': {'dupr_id': '6ZLLQQ', 'rating': 3.532},
        'Nick Segura': {'dupr_id': '1NVRLN', 'rating': 3.816},
        'Matthew Stephens': {'dupr_id': 'W6W9OG', 'rating': 4.488},
        'Mike Hedges': {'dupr_id': '3XQMQ5', 'rating': 4.049},
        'Sean Tansey': {'dupr_id': 'W6DE7Y', 'rating': 3.995},
        'John Marcelia': {'dupr_id': 'YN0QR4', 'rating': 4.011}
    }
    
    # Numeric ID mapping for API calls
    numeric_ids = {
        'Jonathan Chui': 4405492894,
        'Kirk White': 7285039969,
        'Milos Koprivica': 4363666385,
        'Robert Kuseski': 5109225170,
        'Thomas Noonan': 5892289277,
        'Michael Fox': 5276996759,
        'Leo Alvarez': 5842721905,
        'Nick Segura': 7856756110,
        'Matthew Stephens': 6468480130,
        'Mike Hedges': 7858246744,
        'Sean Tansey': 8289162435,
        'John Marcelia': 4363666385
    }
    
    print('🎯 MATCH PREDICTIONS & RATING TARGETS:')
    print('-' * 80)
    
    for match in matches:
        round_name = match.get('round', 'Unknown Round')
        team1 = match.get('team1', [])
        team2 = match.get('team2', [])
        
        print(f'\\n{round_name}')
        print('-' * 50)
        print(f'Team 1: {team1[0]} & {team1[1]}')
        print(f'Team 2: {team2[0]} & {team2[1]}')
        
        # Get player ratings
        team1_ratings = []
        team2_ratings = []
        
        for player in team1:
            if player in player_db:
                team1_ratings.append(player_db[player]['rating'])
            else:
                print(f'  ⚠️  Unknown player: {player}')
                team1_ratings.append(3.0)  # Default rating
        
        for player in team2:
            if player in player_db:
                team2_ratings.append(player_db[player]['rating'])
            else:
                print(f'  ⚠️  Unknown player: {player}')
                team2_ratings.append(3.0)  # Default rating
        
        # Calculate average ratings
        team1_avg = sum(team1_ratings) / len(team1_ratings)
        team2_avg = sum(team2_ratings) / len(team2_ratings)
        
        print(f'  Team 1 Avg Rating: {team1_avg:.3f}')
        print(f'  Team 2 Avg Rating: {team2_avg:.3f}')
        
        # Get expected scores from DUPR API
        try:
            team1_numeric = [numeric_ids.get(p, 0) for p in team1]
            team2_numeric = [numeric_ids.get(p, 0) for p in team2]
            
            teams = [
                {'player1Id': team1_numeric[0], 'player2Id': team1_numeric[1]},
                {'player1Id': team2_numeric[0], 'player2Id': team2_numeric[1]}
            ]
            
            rc, results = dupr.get_expected_score(teams)
            
            if rc == 200 and results:
                teams_result = results.get('teams', [])
                if len(teams_result) >= 2:
                    team1_score = teams_result[0].get('score', 'N/A')
                    team2_score = teams_result[1].get('score', 'N/A')
                    
                    print(f'\\n📊 Expected Scores:')
                    print(f'  {team1[0]} & {team1[1]}: {team1_score}')
                    print(f'  {team2[0]} & {team2[1]}: {team2_score}')
                    
                    # Determine winner and rating implications
                    if isinstance(team1_score, (int, float)) and isinstance(team2_score, (int, float)):
                        if team1_score > team2_score:
                            winner = f'{team1[0]} & {team1[1]}'
                            margin = team1_score - team2_score
                            print(f'🏆 Predicted Winner: {winner}')
                            print(f'   Margin: +{margin:.1f} points')
                            
                            # Rating improvement analysis
                            if team1_avg > team2_avg:
                                print(f'   💡 Team 1 favored - win by {margin:.1f}+ for max rating gain')
                            else:
                                print(f'   💡 Team 1 underdog - any win = big rating boost!')
                                
                        elif team2_score > team1_score:
                            winner = f'{team2[0]} & {team2[1]}'
                            margin = team2_score - team1_score
                            print(f'🏆 Predicted Winner: {winner}')
                            print(f'   Margin: +{margin:.1f} points')
                            
                            # Rating improvement analysis
                            if team2_avg > team1_avg:
                                print(f'   💡 Team 2 favored - win by {margin:.1f}+ for max rating gain')
                            else:
                                print(f'   💡 Team 2 underdog - any win = big rating boost!')
                        else:
                            print(f'🤝 Predicted: Tie')
                            print(f'   💡 Very competitive - any win = significant rating boost!')
                else:
                    print('❌ Invalid response format')
            else:
                print(f'❌ Failed to get expected score (status: {rc})')
                
        except Exception as e:
            print(f'❌ Error getting expected score: {e}')
            # Fallback to rating-based prediction
            rating_diff = abs(team1_avg - team2_avg)
            if rating_diff < 0.1:
                print(f'📊 Rating-based prediction: Very close match (diff: {rating_diff:.3f})')
            elif team1_avg > team2_avg:
                print(f'📊 Rating-based prediction: {team1[0]} & {team1[1]} favored')
            else:
                print(f'📊 Rating-based prediction: {team2[0]} & {team2[1]} favored')

def create_match_template():
    """Create a template file for match analysis"""
    template = {
        "matches": [
            {
                "round": "Round 1",
                "team1": ["Player1", "Player2"],
                "team2": ["Player3", "Player4"]
            },
            {
                "round": "Round 2", 
                "team1": ["Player5", "Player6"],
                "team2": ["Player7", "Player8"]
            }
        ]
    }
    
    with open('match_template.json', 'w') as f:
        json.dump(template, f, indent=2)
    
    print('📝 Created match_template.json')
    print('Edit this file with your actual matches and run:')
    print('python3 match_analyzer.py match_template.json')

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == 'create-template':
            create_match_template()
        else:
            analyze_matches(sys.argv[1])
    else:
        print('Usage:')
        print('  python3 match_analyzer.py create-template')
        print('  python3 match_analyzer.py <match_file.json>')
