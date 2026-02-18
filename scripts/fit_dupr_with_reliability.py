#!/usr/bin/env python3
"""
Fit DUPR model WITH reliability included.
Formula: impact = K * (actual_games - expected_games) * g(reliability)
"""

import csv
import json
import numpy as np
from scipy.optimize import minimize
from pathlib import Path

def load_data(csv_path):
    """Load match data with reliability"""
    matches = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                match = {
                    'r1': float(row['r1']),
                    'r2': float(row['r2']),
                    'r3': float(row['r3']),
                    'r4': float(row['r4']),
                    'games1': int(row['games1']),
                    'games2': int(row['games2']),
                    'winner': int(row['winner']),
                    'imp1': float(row['imp1']),
                    'imp2': float(row['imp2']),
                    'imp3': float(row['imp3']),
                    'imp4': float(row['imp4']),
                }
                # Get reliability (if available)
                rels = []
                for i in range(1,5):
                    rel_key = f'rel{i}'
                    if rel_key in row and row[rel_key]:
                        try:
                            rels.append(float(row[rel_key]))
                        except (ValueError, TypeError):
                            rels.append(None)
                    else:
                        rels.append(None)
                
                match['rel1'], match['rel2'], match['rel3'], match['rel4'] = rels
                matches.append(match)
            except (ValueError, KeyError) as e:
                continue
    return matches

def expected_games(r1, r2, r3, r4, scale=400):
    """Calculate expected games for team 1"""
    team1_avg = (r1 + r2) / 2
    team2_avg = (r3 + r4) / 2
    rating_diff = team1_avg - team2_avg
    prob_win = 1 / (1 + 10 ** (-rating_diff * scale / 400))
    return prob_win * 22

def reliability_multiplier(reliability, func_type='inverse', params=None):
    """Calculate reliability multiplier"""
    if reliability is None:
        return 1.0  # Default if not available
    
    if func_type == 'inverse':
        # g(rel) = a / (1 + rel/b)
        a = params.get('a', 1.0) if params else 1.0
        b = params.get('b', 100.0) if params else 100.0
        return a / (1.0 + reliability / b)
    elif func_type == 'linear':
        # g(rel) = max(0.1, min(2.0, c - d*rel))
        c = params.get('c', 2.0) if params else 2.0
        d = params.get('d', 0.01) if params else 0.01
        multiplier = c - d * reliability
        return max(0.1, min(2.0, multiplier))
    else:
        return 1.0 / (1.0 + reliability / 100.0)

def predict_impacts(match, K, scale, rel_func='inverse', rel_params=None):
    """Predict impacts with reliability"""
    exp_g1 = expected_games(match['r1'], match['r2'], match['r3'], match['r4'], scale)
    actual_g1 = match['games1']
    result_diff = actual_g1 - exp_g1
    
    # Get reliability multipliers
    g1 = reliability_multiplier(match.get('rel1'), rel_func, rel_params)
    g2 = reliability_multiplier(match.get('rel2'), rel_func, rel_params)
    g3 = reliability_multiplier(match.get('rel3'), rel_func, rel_params)
    g4 = reliability_multiplier(match.get('rel4'), rel_func, rel_params)
    
    if match['winner'] == 1:
        return (
            K * result_diff * 0.5 * g1,
            K * result_diff * 0.5 * g2,
            -K * result_diff * 0.5 * g3,
            -K * result_diff * 0.5 * g4
        )
    else:
        return (
            -K * result_diff * 0.5 * g1,
            -K * result_diff * 0.5 * g2,
            K * result_diff * 0.5 * g3,
            K * result_diff * 0.5 * g4
        )

def loss_function_inverse(params, matches):
    """Loss function for inverse reliability: g(rel) = a / (1 + rel/b)"""
    K, scale, a, b = params
    errors = []
    for m in matches:
        rel_params = {'a': a, 'b': b}
        p1, p2, p3, p4 = predict_impacts(m, K, scale, 'inverse', rel_params)
        errors.extend([
            (p1 - m['imp1'])**2,
            (p2 - m['imp2'])**2,
            (p3 - m['imp3'])**2,
            (p4 - m['imp4'])**2
        ])
    return np.mean(errors)

def main():
    csv_path = Path(__file__).resolve().parent.parent / "match_rating_data.csv"
    
    print("="*80)
    print("FITTING DUPR MODEL WITH RELIABILITY")
    print("="*80)
    
    print("\n[001] Loading match data...")
    all_matches = load_data(csv_path)
    print(f"[002] Loaded {len(all_matches)} total matches")
    
    # Filter to matches with reliability
    matches_with_rel = [m for m in all_matches if all(m.get(f'rel{i}') is not None for i in range(1,5))]
    print(f"[003] Matches with reliability: {len(matches_with_rel)}/{len(all_matches)}")
    
    if len(matches_with_rel) < 100:
        print(f"\n[WARN] Only {len(matches_with_rel)} matches with reliability!")
        print("[WARN] Need at least 100 matches for reliable fitting.")
        print("[WARN] Using all matches (reliability will default to 1.0 if missing)")
        train_matches = all_matches
    else:
        train_matches = matches_with_rel
        print(f"[004] Using {len(train_matches)} matches with reliability for training")
    
    # Split train/test
    split_idx = int(len(train_matches) * 0.8)
    train_data = train_matches[:split_idx]
    test_data = train_matches[split_idx:]
    print(f"[005] Train: {len(train_data)}, Test: {len(test_data)}")
    
    print("\n[006] Fitting model parameters (K, scale, reliability params)...")
    print("[007] This may take 1-2 minutes...")
    
    # Fit with inverse reliability function: g(rel) = a / (1 + rel/b)
    try:
        result = minimize(
            loss_function_inverse,
            x0=[0.01, 400, 1.0, 100.0],  # K, scale, a, b
            args=(train_data,),
            method='Nelder-Mead',
            options={'maxiter': 1000}
        )
        
        K_fitted = result.x[0]
        scale_fitted = result.x[1]
        a_fitted = result.x[2]
        b_fitted = result.x[3]
        
        print(f"\n[008] ✓ Fitting complete!")
        print(f"[009] K (step size): {K_fitted:.8f}")
        print(f"[010] Scale (ELO): {scale_fitted:.2f}")
        print(f"[011] Reliability function: g(rel) = {a_fitted:.4f} / (1 + rel/{b_fitted:.2f})")
        
    except Exception as e:
        print(f"\n[ERR] Fitting failed: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to simple fit without reliability params
        K_fitted, scale_fitted, a_fitted, b_fitted = 0.0005, 1500, 1.0, 100.0
    
    # Evaluate on test set
    print("\n[012] Evaluating on test set...")
    test_errors = []
    rel_params = {'a': a_fitted, 'b': b_fitted}
    
    for m in test_data:
        p1, p2, p3, p4 = predict_impacts(m, K_fitted, scale_fitted, 'inverse', rel_params)
        test_errors.extend([
            abs(p1 - m['imp1']),
            abs(p2 - m['imp2']),
            abs(p3 - m['imp3']),
            abs(p4 - m['imp4'])
        ])
    
    mae = np.mean(test_errors)
    rmse = np.sqrt(np.mean([e**2 for e in test_errors]))
    
    # Calculate correlation
    predicted = []
    actual = []
    for m in test_data:
        p1, p2, p3, p4 = predict_impacts(m, K_fitted, scale_fitted, 'inverse', rel_params)
        predicted.extend([p1, p2, p3, p4])
        actual.extend([m['imp1'], m['imp2'], m['imp3'], m['imp4']])
    
    correlation = np.corrcoef(predicted, actual)[0, 1]
    
    print(f"[013] Test MAE: {mae:.8f}")
    print(f"[014] Test RMSE: {rmse:.8f}")
    print(f"[015] Test Correlation: {correlation:.6f}")
    
    # Save model
    model_file = Path(__file__).resolve().parent.parent / "dupr_model.json"
    model_data = {
        'K': float(K_fitted),
        'scale': float(scale_fitted),
        'reliability_func': 'inverse',
        'reliability_params': {
            'a': float(a_fitted),
            'b': float(b_fitted)
        },
        'mae': float(mae),
        'rmse': float(rmse),
        'correlation': float(correlation),
        'n_train': len(train_data),
        'n_test': len(test_data),
        'n_matches_with_reliability': len(matches_with_rel),
        'formula': 'impact = K * (actual_games - expected_games) * sign * g(reliability)',
        'g_formula': f'g(rel) = {a_fitted:.4f} / (1 + rel/{b_fitted:.2f})'
    }
    
    with open(model_file, 'w') as f:
        json.dump(model_data, f, indent=2)
    
    print(f"\n[016] ✓ Model saved to {model_file}")
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Formula: impact = K * (actual_games - expected_games) * sign * g(reliability)")
    print(f"  K = {K_fitted:.8f}")
    print(f"  Expected games uses ELO with scale = {scale_fitted:.2f}")
    print(f"  Reliability multiplier: g(rel) = {a_fitted:.4f} / (1 + rel/{b_fitted:.2f})")
    print(f"  Test MAE: {mae:.8f}")
    print(f"  Test RMSE: {rmse:.8f}")
    print(f"  Test Correlation: {correlation:.6f}")
    print("="*80)

if __name__ == "__main__":
    main()
