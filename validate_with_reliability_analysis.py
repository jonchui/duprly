#!/usr/bin/env python3
"""
Analyze how reliability affects predictions and show we need to refit the model.
"""

import csv
import numpy as np
from dupr_predictor import DuprPredictor

def load_matches(csv_file, n_matches=1000):
    """Load the last N matches from CSV"""
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
            })
    return matches[-n_matches:] if len(matches) > n_matches else matches

def evaluate_with_reliability(predictor, matches, reliability_value):
    """Evaluate with a fixed reliability value for all players"""
    predicted = []
    actual = []
    
    for match in matches:
        pred_imp1, pred_imp2, pred_imp3, pred_imp4 = predictor.predict_impacts(
            match['r1'], match['r2'], match['r3'], match['r4'],
            match['games1'], match['games2'], match['winner'],
            rel1=reliability_value, rel2=reliability_value,
            rel3=reliability_value, rel4=reliability_value
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
    
    return mae, rmse, correlation, np.mean(np.abs(predicted)), np.mean(np.abs(actual))

if __name__ == "__main__":
    print("Loading predictor and matches...")
    predictor = DuprPredictor('dupr_model.json')
    matches = load_matches('match_rating_data.csv', n_matches=1000)
    print(f"Loaded {len(matches)} matches\n")
    
    print("="*70)
    print("ANALYSIS: Impact of Reliability on Predictions")
    print("="*70)
    print("\nTesting different reliability values (0-100 scale):")
    print("-"*70)
    print(f"{'Reliability':<15} {'MAE':<12} {'RMSE':<12} {'Correlation':<12} {'Avg |Pred|':<12} {'Avg |Actual|':<12}")
    print("-"*70)
    
    # Test different reliability values
    test_reliabilities = [None, 0, 20, 40, 50, 60, 80, 100]
    
    best_mae = float('inf')
    best_rel = None
    
    for rel in test_reliabilities:
        if rel is None:
            rel_str = "None (default)"
            mae, rmse, corr, avg_pred, avg_actual = evaluate_with_reliability(predictor, matches, None)
        else:
            rel_str = str(rel)
            mae, rmse, corr, avg_pred, avg_actual = evaluate_with_reliability(predictor, matches, rel)
        
        if mae < best_mae:
            best_mae = mae
            best_rel = rel
        
        print(f"{rel_str:<15} {mae:<12.6f} {rmse:<12.6f} {corr:<12.6f} {avg_pred:<12.6f} {avg_actual:<12.6f}")
    
    print("-"*70)
    print(f"\nBest reliability (lowest MAE): {best_rel}")
    print(f"Best MAE: {best_mae:.6f}")
    
    print("\n" + "="*70)
    print("KEY INSIGHT:")
    print("="*70)
    print("The current model was fitted WITHOUT reliability.")
    print("When we add reliability multipliers, predictions become smaller")
    print("because the K value was already calibrated for average reliability.")
    print("\nSOLUTION:")
    print("We need to REFIT the model WITH reliability data!")
    print("The formula should be: impact = K * (result_diff) * g(reliability)")
    print("where K and g() are fitted together on matches with known reliability.")
    print("="*70)
    
    # Show what the reliability multiplier does
    print("\nReliability Multiplier Examples (inverse function):")
    print("-"*70)
    for rel in [0, 20, 40, 50, 60, 80, 100]:
        mult = predictor.reliability_multiplier(rel)
        print(f"  Reliability {rel:3d} → Multiplier: {mult:.4f} ({'HIGH' if mult > 1.0 else 'LOW'} impact)")
    print("-"*70)
