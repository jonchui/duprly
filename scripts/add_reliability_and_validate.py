#!/usr/bin/env python3
"""
Fetch reliability for matches and add to CSV, then validate predictor accuracy.
This shows how much reliability improves predictions.
"""

import json
import csv
import sys
import os
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dupr_client import DuprClient
from dotenv import load_dotenv
from dupr_predictor import DuprPredictor
import numpy as np

load_dotenv()

def get_player_ids_from_match(match_json):
    """Extract player IDs from match JSON"""
    try:
        data = match_json if isinstance(match_json, dict) else json.loads(match_json)
        teams = data.get("teams", [])
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
    except Exception as e:
        return None

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

def load_matches_with_reliability(csv_file, dupr_client, n_matches=1000):
    """Load matches and fetch reliability"""
    matches = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            matches.append({
                'match_id': row['match_id'],
                'r1': float(row['r1']),
                'r2': float(row['r2']),
                'r3': float(row['r3']),
                'r4': float(row['r4']),
                'games1': int(row['games1']),
                'games2': int(row['games2']),
                'winner': int(row['winner']),
                'actual_imp1': float(row['imp1']),
                'actual_imp2': float(row['imp2']),
                'actual_imp3': float(row['imp3']),
                'actual_imp4': float(row['imp4']),
                'player_ids': None,  # Will be filled from DB
            })
    
    matches = matches[-n_matches:] if len(matches) > n_matches else matches
    
    # Fetch reliability for matches
    print(f"Fetching reliability for {len(matches)} matches...")
    print("(This may take a while - fetching player data from API)")
    
    # Load match JSON from DB to get player IDs
    try:
        from dupr_db import open_db, ClubMatchRaw
        from sqlalchemy import select
        
        eng = open_db()
        match_dict = {m['match_id']: m for m in matches}
        
        with eng.connect() as conn:
            result = conn.execute(select(ClubMatchRaw))
            for r in result:
                match_id = str(r.match_id)
                if match_id in match_dict:
                    player_ids = get_player_ids_from_match(r.raw_json)
                    if player_ids:
                        match_dict[match_id]['player_ids'] = player_ids
        
        # Fetch reliability for each player
        reliability_fetched = 0
        for i, match in enumerate(matches, 1):
            if i % 50 == 0:
                print(f"  Progress: {i}/{len(matches)} matches processed, {reliability_fetched} with reliability")
            
            if not match['player_ids']:
                continue
            
            rels = []
            for pid in match['player_ids']:
                try:
                    rc, player_data = dupr_client.get_player(pid)
                    if rc == 200 and player_data:
                        rel = get_reliability_from_player(player_data)
                        rels.append(rel)
                    else:
                        rels.append(None)
                    time.sleep(0.1)  # Rate limit
                except Exception:
                    rels.append(None)
            
            if all(r is not None for r in rels):
                match['rel1'] = rels[0]
                match['rel2'] = rels[1]
                match['rel3'] = rels[2]
                match['rel4'] = rels[3]
                reliability_fetched += 1
        
        print(f"\nFetched reliability for {reliability_fetched}/{len(matches)} matches")
        
    except ImportError:
        print("Warning: Could not import database modules. Skipping reliability fetch.")
        print("Matches will be evaluated without reliability.")
    
    return matches

def evaluate_predictor(predictor, matches, use_reliability=True):
    """Evaluate predictor with and without reliability"""
    predicted = []
    actual = []
    
    for match in matches:
        if use_reliability and all(match.get(f'rel{i}') is not None for i in range(1,5)):
            pred_imp1, pred_imp2, pred_imp3, pred_imp4 = predictor.predict_impacts(
                match['r1'], match['r2'], match['r3'], match['r4'],
                match['games1'], match['games2'], match['winner'],
                rel1=match['rel1'], rel2=match['rel2'],
                rel3=match['rel3'], rel4=match['rel4']
            )
        else:
            pred_imp1, pred_imp2, pred_imp3, pred_imp4 = predictor.predict_impacts(
                match['r1'], match['r2'], match['r3'], match['r4'],
                match['games1'], match['games2'], match['winner']
            )
        
        predicted.extend([pred_imp1, pred_imp2, pred_imp3, pred_imp4])
        actual.extend([
            match['actual_imp1'], match['actual_imp2'],
            match['actual_imp3'], match['actual_imp4']
        ])
    
    predicted = np.array(predicted)
    actual = np.array(actual)
    
    mae = np.mean(np.abs(predicted - actual))
    rmse = np.sqrt(np.mean((predicted - actual) ** 2))
    correlation = np.corrcoef(predicted, actual)[0, 1]
    mean_pred = np.mean(np.abs(predicted))
    mean_actual = np.mean(np.abs(actual))
    
    return {
        'mae': mae,
        'rmse': rmse,
        'correlation': correlation,
        'mean_pred': mean_pred,
        'mean_actual': mean_actual
    }

if __name__ == "__main__":
    print("="*80)
    print("EVALUATING PREDICTOR: With vs Without Reliability")
    print("="*80)
    
    # Authenticate
    print("\nAuthenticating with DUPR API...")
    dupr = DuprClient(verbose=False)
    username = os.getenv("DUPR_USERNAME")
    password = os.getenv("DUPR_PASSWORD")
    if username and password:
        dupr.auth_user(username, password)
        print("✓ Authenticated")
    else:
        print("⚠️  No credentials - will skip reliability fetch")
        dupr = None
    
    # Load predictor
    print("\nLoading predictor...")
    predictor = DuprPredictor('dupr_model.json')
    
    # Load matches
    print("\nLoading matches from CSV...")
    if dupr:
        matches = load_matches_with_reliability('match_rating_data.csv', dupr, n_matches=1000)
    else:
        # Load without reliability fetch
        matches = []
        with open('match_rating_data.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                matches.append({
                    'match_id': row['match_id'],
                    'r1': float(row['r1']),
                    'r2': float(row['r2']),
                    'r3': float(row['r3']),
                    'r4': float(row['r4']),
                    'games1': int(row['games1']),
                    'games2': int(row['games2']),
                    'winner': int(row['winner']),
                    'actual_imp1': float(row['imp1']),
                    'actual_imp2': float(row['imp2']),
                    'actual_imp3': float(row['imp3']),
                    'actual_imp4': float(row['imp4']),
                })
        matches = matches[-1000:] if len(matches) > 1000 else matches
    
    print(f"Loaded {len(matches)} matches")
    
    # Count matches with reliability
    matches_with_rel = sum(1 for m in matches if all(m.get(f'rel{i}') is not None for i in range(1,5)))
    print(f"Matches with reliability: {matches_with_rel}/{len(matches)}")
    
    # Evaluate WITHOUT reliability
    print("\n" + "="*80)
    print("EVALUATION WITHOUT RELIABILITY")
    print("="*80)
    results_no_rel = evaluate_predictor(predictor, matches, use_reliability=False)
    print(f"MAE:  {results_no_rel['mae']:.6f}")
    print(f"RMSE: {results_no_rel['rmse']:.6f}")
    print(f"Correlation: {results_no_rel['correlation']:.6f}")
    print(f"Mean |Predicted|: {results_no_rel['mean_pred']:.6f}")
    print(f"Mean |Actual|:    {results_no_rel['mean_actual']:.6f}")
    
    # Evaluate WITH reliability (if available)
    if matches_with_rel > 0:
        print("\n" + "="*80)
        print(f"EVALUATION WITH RELIABILITY ({matches_with_rel} matches)")
        print("="*80)
        results_with_rel = evaluate_predictor(predictor, matches, use_reliability=True)
        print(f"MAE:  {results_with_rel['mae']:.6f}")
        print(f"RMSE: {results_with_rel['rmse']:.6f}")
        print(f"Correlation: {results_with_rel['correlation']:.6f}")
        print(f"Mean |Predicted|: {results_with_rel['mean_pred']:.6f}")
        print(f"Mean |Actual|:    {results_with_rel['mean_actual']:.6f}")
        
        # Compare
        print("\n" + "="*80)
        print("IMPROVEMENT WITH RELIABILITY")
        print("="*80)
        mae_improvement = ((results_no_rel['mae'] - results_with_rel['mae']) / results_no_rel['mae']) * 100
        rmse_improvement = ((results_no_rel['rmse'] - results_with_rel['rmse']) / results_no_rel['rmse']) * 100
        corr_improvement = results_with_rel['correlation'] - results_no_rel['correlation']
        
        print(f"MAE improvement:  {mae_improvement:+.2f}% ({results_no_rel['mae']:.6f} → {results_with_rel['mae']:.6f})")
        print(f"RMSE improvement: {rmse_improvement:+.2f}% ({results_no_rel['rmse']:.6f} → {results_with_rel['rmse']:.6f})")
        print(f"Correlation change: {corr_improvement:+.6f} ({results_no_rel['correlation']:.6f} → {results_with_rel['correlation']:.6f})")
        
        if mae_improvement > 0:
            print(f"\n✅ Reliability improves MAE by {mae_improvement:.2f}%")
        else:
            print(f"\n⚠️  Reliability doesn't improve MAE (model needs refitting with reliability)")
    else:
        print("\n⚠️  No matches with reliability data. Cannot compare.")
        print("Note: The model was fitted WITHOUT reliability, so adding reliability")
        print("multipliers may make predictions worse until we refit the model.")
