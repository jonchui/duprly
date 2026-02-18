#!/usr/bin/env python3
"""
Validate DUPR Predictor WITH reliability on matches from CSV.
Shows improvement over model without reliability.
"""

import csv
import json
import sys
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
    
    return matches[-n_matches:] if len(matches) > n_matches else matches

def evaluate_predictor(predictor, matches, use_reliability=True):
    """Evaluate predictor accuracy"""
    predicted_impacts = []
    actual_impacts = []
    
    matches_with_rel = 0
    
    for match in matches:
        # Check if we have reliability
        has_rel = all(match.get(f'rel{i}') is not None for i in range(1,5))
        if has_rel:
            matches_with_rel += 1
        
        # Predict impacts
        if use_reliability and has_rel:
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
    
    # Additional statistics
    errors = predicted_impacts - actual_impacts
    mean_error = np.mean(errors)
    std_error = np.std(errors)
    
    abs_errors = np.abs(errors)
    p50 = np.percentile(abs_errors, 50)
    p75 = np.percentile(abs_errors, 75)
    p90 = np.percentile(abs_errors, 90)
    p95 = np.percentile(abs_errors, 95)
    
    return {
        'mae': mae,
        'rmse': rmse,
        'correlation': correlation,
        'mean_error': mean_error,
        'std_error': std_error,
        'p50': p50,
        'p75': p75,
        'p90': p90,
        'p95': p95,
        'n_matches': len(matches),
        'n_predictions': len(predicted_impacts),
        'matches_with_rel': matches_with_rel,
        'mean_pred': np.mean(np.abs(predicted_impacts)),
        'mean_actual': np.mean(np.abs(actual_impacts))
    }

if __name__ == "__main__":
    print("="*80)
    print("DUPR PREDICTOR VALIDATION (WITH RELIABILITY)")
    print("="*80)
    
    print("\n[001] Loading predictor...")
    try:
        predictor = DuprPredictor('dupr_model.json')
        print(f"[002] ✓ Loaded model:")
        print(f"     K = {predictor.K:.8f}")
        print(f"     Scale = {predictor.scale:.2f}")
        print(f"     Reliability func = {predictor.reliability_func}")
        if predictor.reliability_params:
            print(f"     Reliability params = {predictor.reliability_params}")
    except Exception as e:
        print(f"[ERR] Failed to load model: {e}")
        exit(1)
    
    print("\n[003] Loading matches from CSV...")
    matches = load_matches('match_rating_data.csv', n_matches=1000)
    print(f"[004] Loaded {len(matches)} matches")
    
    matches_with_rel = sum(1 for m in matches if all(m.get(f'rel{i}') is not None for i in range(1,5)))
    print(f"[005] Matches with reliability: {matches_with_rel}/{len(matches)}")
    
    if matches_with_rel == 0:
        print("\n[WARN] No reliability data found!")
        print("[WARN] Run: python scripts/extract_match_rating_data.py")
        print("[WARN] Then: python scripts/fit_dupr_with_reliability.py")
        exit(1)
    
    print("\n[006] Evaluating predictor WITHOUT reliability...")
    results_no_rel = evaluate_predictor(predictor, matches, use_reliability=False)
    
    print("\n[007] Evaluating predictor WITH reliability...")
    results_with_rel = evaluate_predictor(predictor, matches, use_reliability=True)
    
    print("\n" + "="*80)
    print("RESULTS: WITHOUT RELIABILITY")
    print("="*80)
    print(f"Matches evaluated: {results_no_rel['n_matches']}")
    print(f"Total predictions: {results_no_rel['n_predictions']}")
    print(f"\nMAE:  {results_no_rel['mae']:.6f}")
    print(f"RMSE: {results_no_rel['rmse']:.6f}")
    print(f"Correlation: {results_no_rel['correlation']:.6f}")
    print(f"Mean |Predicted|: {results_no_rel['mean_pred']:.6f}")
    print(f"Mean |Actual|:    {results_no_rel['mean_actual']:.6f}")
    
    print("\n" + "="*80)
    print(f"RESULTS: WITH RELIABILITY ({results_with_rel['matches_with_rel']} matches)")
    print("="*80)
    print(f"Matches evaluated: {results_with_rel['n_matches']}")
    print(f"Matches with reliability: {results_with_rel['matches_with_rel']}")
    print(f"Total predictions: {results_with_rel['n_predictions']}")
    print(f"\nMAE:  {results_with_rel['mae']:.6f}")
    print(f"RMSE: {results_with_rel['rmse']:.6f}")
    print(f"Correlation: {results_with_rel['correlation']:.6f}")
    print(f"Mean |Predicted|: {results_with_rel['mean_pred']:.6f}")
    print(f"Mean |Actual|:    {results_with_rel['mean_actual']:.6f}")
    
    print("\nError Statistics:")
    print(f"  Mean error (bias): {results_with_rel['mean_error']:.6f}")
    print(f"  Std deviation: {results_with_rel['std_error']:.6f}")
    print(f"\nAbsolute Error Percentiles:")
    print(f"  50th (median): {results_with_rel['p50']:.6f}")
    print(f"  75th: {results_with_rel['p75']:.6f}")
    print(f"  90th: {results_with_rel['p90']:.6f}")
    print(f"  95th: {results_with_rel['p95']:.6f}")
    
    # Compare
    print("\n" + "="*80)
    print("IMPROVEMENT WITH RELIABILITY")
    print("="*80)
    mae_improvement = ((results_no_rel['mae'] - results_with_rel['mae']) / results_no_rel['mae']) * 100
    rmse_improvement = ((results_no_rel['rmse'] - results_with_rel['rmse']) / results_no_rel['rmse']) * 100
    corr_improvement = results_with_rel['correlation'] - results_no_rel['correlation']
    pred_magnitude_improvement = ((results_with_rel['mean_pred'] - results_no_rel['mean_pred']) / results_no_rel['mean_pred']) * 100
    
    print(f"MAE improvement:  {mae_improvement:+.2f}%")
    print(f"                ({results_no_rel['mae']:.6f} → {results_with_rel['mae']:.6f})")
    print(f"\nRMSE improvement: {rmse_improvement:+.2f}%")
    print(f"                 ({results_no_rel['rmse']:.6f} → {results_with_rel['rmse']:.6f})")
    print(f"\nCorrelation change: {corr_improvement:+.6f}")
    print(f"                   ({results_no_rel['correlation']:.6f} → {results_with_rel['correlation']:.6f})")
    print(f"\nPrediction magnitude change: {pred_magnitude_improvement:+.2f}%")
    print(f"                            ({results_no_rel['mean_pred']:.6f} → {results_with_rel['mean_pred']:.6f})")
    
    if mae_improvement > 0:
        print(f"\n✅ Reliability improves MAE by {mae_improvement:.2f}%")
    else:
        print(f"\n⚠️  MAE didn't improve - model may need more data or different reliability function")
    
    if corr_improvement > 0.1:
        print(f"✅ Correlation improved significantly (+{corr_improvement:.4f})")
    elif corr_improvement > 0:
        print(f"✓ Correlation improved slightly (+{corr_improvement:.4f})")
    else:
        print(f"⚠️  Correlation didn't improve - may need more matches with reliability")
    
    print("\n" + "="*80)
