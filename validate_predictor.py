#!/usr/bin/env python3
"""
Validate DUPR Predictor on last 1000 matches from CSV
"""

import csv
import json
import numpy as np
from dupr_predictor import DuprPredictor

def load_matches(csv_file, n_matches=1000):
    """Load the last N matches from CSV"""
    matches = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            match_data = {
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
            }
            # Add reliability if available
            for i in range(1, 5):
                rel_key = f'rel{i}'
                if rel_key in row and row[rel_key]:
                    try:
                        match_data[rel_key] = float(row[rel_key])
                    except (ValueError, TypeError):
                        match_data[rel_key] = None
                else:
                    match_data[rel_key] = None
            matches.append(match_data)
    
    # Return last N matches
    return matches[-n_matches:] if len(matches) > n_matches else matches

def evaluate_predictor(predictor, matches):
    """Evaluate predictor accuracy"""
    predicted_impacts = []
    actual_impacts = []
    
    for match in matches:
        # Predict impacts (with reliability if available)
        pred_imp1, pred_imp2, pred_imp3, pred_imp4 = predictor.predict_impacts(
            match['r1'], match['r2'], match['r3'], match['r4'],
            match['games1'], match['games2'], match['winner'],
            rel1=match.get('rel1'), rel2=match.get('rel2'),
            rel3=match.get('rel3'), rel4=match.get('rel4')
        )
        
        # Store predictions and actuals
        predicted_impacts.extend([pred_imp1, pred_imp2, pred_imp3, pred_imp4])
        actual_impacts.extend([
            match['actual_imp1'], match['actual_imp2'],
            match['actual_imp3'], match['actual_imp4']
        ])
    
    predicted_impacts = np.array(predicted_impacts)
    actual_impacts = np.array(actual_impacts)
    
    # Calculate metrics
    mae = np.mean(np.abs(predicted_impacts - actual_impacts))
    rmse = np.sqrt(np.mean((predicted_impacts - actual_impacts) ** 2))
    correlation = np.corrcoef(predicted_impacts, actual_impacts)[0, 1]
    
    # Mean absolute percentage error (avoid division by zero)
    mape = np.mean(np.abs((predicted_impacts - actual_impacts) / (actual_impacts + 1e-10))) * 100
    
    # Additional statistics
    errors = predicted_impacts - actual_impacts
    mean_error = np.mean(errors)
    std_error = np.std(errors)
    
    # Percentiles of absolute errors
    abs_errors = np.abs(errors)
    p50 = np.percentile(abs_errors, 50)
    p75 = np.percentile(abs_errors, 75)
    p90 = np.percentile(abs_errors, 90)
    p95 = np.percentile(abs_errors, 95)
    
    return {
        'mae': mae,
        'rmse': rmse,
        'correlation': correlation,
        'mape': mape,
        'mean_error': mean_error,
        'std_error': std_error,
        'p50': p50,
        'p75': p75,
        'p90': p90,
        'p95': p95,
        'n_matches': len(matches),
        'n_predictions': len(predicted_impacts),
        'predicted': predicted_impacts,
        'actual': actual_impacts,
        'errors': errors
    }

if __name__ == "__main__":
    print("Loading DUPR Predictor...")
    predictor = DuprPredictor('dupr_model.json')
    
    print("Loading matches from CSV...")
    matches = load_matches('match_rating_data.csv', n_matches=1000)
    print(f"Loaded {len(matches)} matches")
    
    print("\nEvaluating predictor...")
    results = evaluate_predictor(predictor, matches)
    
    print("\n" + "="*60)
    print("PREDICTOR ACCURACY RESULTS")
    print("="*60)
    print(f"Number of matches evaluated: {results['n_matches']}")
    print(f"Total predictions (4 players × matches): {results['n_predictions']}")
    # Count how many matches have reliability data
    matches_with_rel = sum(1 for m in matches if m.get('rel1') is not None)
    
    print(f"\nMean Absolute Error (MAE): {results['mae']:.6f}")
    print(f"Root Mean Squared Error (RMSE): {results['rmse']:.6f}")
    print(f"Correlation (predicted vs actual): {results['correlation']:.6f}")
    print(f"Mean Absolute Percentage Error (MAPE): {results['mape']:.2f}%")
    print(f"\nReliability data: {matches_with_rel}/{len(matches)} matches have reliability")
    if matches_with_rel == 0:
        print("  ⚠️  WARNING: No reliability data found! Predictions may be inaccurate.")
        print("  Run: python scripts/add_reliability_to_csv.py to add reliability data")
        print("\n  ⚠️  CRITICAL: The model was fitted WITHOUT reliability!")
        print("     When reliability multipliers are applied, predictions become smaller.")
        print("     You need to REFIT the model WITH reliability data.")
        print("     Formula should be: impact = K * (result_diff) * g(reliability)")
        print("     where K and g() are fitted together.")
    print(f"\nError Statistics:")
    print(f"  Mean error (bias): {results['mean_error']:.6f}")
    print(f"  Std deviation of errors: {results['std_error']:.6f}")
    print(f"\nAbsolute Error Percentiles:")
    print(f"  50th percentile (median): {results['p50']:.6f}")
    print(f"  75th percentile: {results['p75']:.6f}")
    print(f"  90th percentile: {results['p90']:.6f}")
    print(f"  95th percentile: {results['p95']:.6f}")
    print("="*60)
    
    # Show some example predictions vs actuals
    print("\nSample Predictions (first 10 matches):")
    print("-" * 80)
    print(f"{'Match':<10} {'Player':<8} {'Predicted':<12} {'Actual':<12} {'Error':<12} {'Abs Error':<12}")
    print("-" * 80)
    
    for i in range(min(10, len(matches))):
        match = matches[i]
        pred_imp1, pred_imp2, pred_imp3, pred_imp4 = predictor.predict_impacts(
            match['r1'], match['r2'], match['r3'], match['r4'],
            match['games1'], match['games2'], match['winner']
        )
        actuals = [match['actual_imp1'], match['actual_imp2'], 
                   match['actual_imp3'], match['actual_imp4']]
        preds = [pred_imp1, pred_imp2, pred_imp3, pred_imp4]
        
        rels = [match.get('rel1'), match.get('rel2'), match.get('rel3'), match.get('rel4')]
        for j, (pred, actual, rel) in enumerate(zip(preds, actuals, rels)):
            error = pred - actual
            abs_error = abs(error)
            rel_str = f"{rel:.0f}" if rel is not None else "N/A"
            print(f"{match['match_id']:<10} P{j+1:<7} {pred:>11.6f} {actual:>11.6f} {error:>11.6f} {abs_error:>11.6f} rel={rel_str:>4}")
    
    # Show model parameters
    print("\nModel Parameters:")
    print(f"  K (learning rate): {predictor.K:.6f}")
    print(f"  Scale: {predictor.scale:.6f}")
