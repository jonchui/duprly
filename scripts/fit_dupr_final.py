#!/usr/bin/env python3
"""
Fit DUPR rating impact model from match_rating_data.csv.
Outputs: fit_results.txt with fitted parameters and accuracy.
"""

import csv
import json
import sys

# Check dependencies
try:
    import numpy as np
    from scipy.optimize import minimize
except ImportError as e:
    print(f"ERROR: Missing dependency: {e}")
    print("Install with: pip install numpy scipy scikit-learn")
    sys.exit(1)

def load_data(csv_path):
    """Load match data from CSV"""
    rows = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                rows.append({
                    'r1': float(r['r1']), 'r2': float(r['r2']),
                    'r3': float(r['r3']), 'r4': float(r['r4']),
                    'imp1': float(r['imp1']), 'imp2': float(r['imp2']),
                    'imp3': float(r['imp3']), 'imp4': float(r['imp4']),
                    'games1': int(r['games1']), 'games2': int(r['games2']),
                    'winner': int(r['winner']),
                })
            except (ValueError, KeyError):
                continue
    return rows

def expected_score_elo(r1, r2, r3, r4, scale=400):
    """ELO-style expected games for team 1"""
    team1_avg = (r1 + r2) / 2
    team2_avg = (r3 + r4) / 2
    rating_diff = team1_avg - team2_avg
    prob_win = 1 / (1 + 10 ** (-rating_diff * scale / 400))
    total_games = 22  # Typical 2-game match
    return prob_win * total_games

def predict_impact_simple(r1, r2, r3, r4, games1, games2, winner, K, scale=400):
    """Predict impact for each player"""
    expected_g1 = expected_score_elo(r1, r2, r3, r4, scale)
    actual_g1 = games1
    result_term = actual_g1 - expected_g1
    
    if winner == 1:
        return K * result_term * 0.5, K * result_term * 0.5, -K * result_term * 0.5, -K * result_term * 0.5
    else:
        return -K * result_term * 0.5, -K * result_term * 0.5, K * result_term * 0.5, K * result_term * 0.5

def loss_function(params, data):
    """Mean squared error loss"""
    K, scale = params
    total_error = 0
    count = 0
    for m in data:
        imp1_p, imp2_p, imp3_p, imp4_p = predict_impact_simple(
            m['r1'], m['r2'], m['r3'], m['r4'],
            m['games1'], m['games2'], m['winner'], K, scale
        )
        total_error += (imp1_p - m['imp1'])**2 + (imp2_p - m['imp2'])**2
        total_error += (imp3_p - m['imp3'])**2 + (imp4_p - m['imp4'])**2
        count += 4
    return total_error / count if count > 0 else 1e10

def main():
    output_lines = []
    def log(msg):
        output_lines.append(str(msg))
        print(msg)
    
    log("="*70)
    log("DUPR ALGORITHM REVERSE-ENGINEERING")
    log("="*70 + "\n")
    
    log("Loading match data...")
    try:
        data = load_data('match_rating_data.csv')
    except FileNotFoundError:
        log("ERROR: match_rating_data.csv not found!")
        log("Run: python scripts/extract_match_rating_data.py first")
        with open('fit_results.txt', 'w') as f:
            f.write('\n'.join(output_lines))
        return
    
    log(f"Loaded {len(data)} matches ({len(data)*4} impact observations)\n")
    
    # Split: 80% train, 20% test
    split_idx = int(len(data) * 0.8)
    train_data = data[:split_idx]
    test_data = data[split_idx:]
    log(f"Train: {len(train_data)} matches")
    log(f"Test: {len(test_data)} matches\n")
    
    # Fit model
    log("Fitting model (K, scale)...")
    log("This may take 30-60 seconds...\n")
    try:
        result = minimize(
            loss_function,
            x0=[0.01, 400],
            args=(train_data,),
            method='Nelder-Mead',
            options={'maxiter': 500, 'xatol': 1e-6}
        )
        K_fit, scale_fit = result.x
    except Exception as e:
        log(f"ERROR during fitting: {e}")
        import traceback
        log(traceback.format_exc())
        with open('fit_results.txt', 'w') as f:
            f.write('\n'.join(output_lines))
        return
    
    log(f"FITTED PARAMETERS:")
    log(f"  K (step size): {K_fit:.8f}")
    log(f"  Scale (ELO): {scale_fit:.2f}\n")
    
    # Evaluate on test set
    log("Evaluating on test set...")
    test_preds = []
    test_actuals = []
    for m in test_data:
        imp1_p, imp2_p, imp3_p, imp4_p = predict_impact_simple(
            m['r1'], m['r2'], m['r3'], m['r4'],
            m['games1'], m['games2'], m['winner'], K_fit, scale_fit
        )
        test_preds.extend([imp1_p, imp2_p, imp3_p, imp4_p])
        test_actuals.extend([m['imp1'], m['imp2'], m['imp3'], m['imp4']])
    
    mae = np.mean([abs(a - p) for a, p in zip(test_actuals, test_preds)])
    rmse = np.sqrt(np.mean([(a - p)**2 for a, p in zip(test_actuals, test_preds)]))
    log(f"  MAE: {mae:.8f}")
    log(f"  RMSE: {rmse:.8f}\n")
    
    # Show examples
    log("EXAMPLE PREDICTIONS (first 5 test matches):")
    for i, m in enumerate(test_data[:5], 1):
        exp_g1 = expected_score_elo(m['r1'], m['r2'], m['r3'], m['r4'], scale_fit)
        imp1_p, imp2_p, imp3_p, imp4_p = predict_impact_simple(
            m['r1'], m['r2'], m['r3'], m['r4'],
            m['games1'], m['games2'], m['winner'], K_fit, scale_fit
        )
        log(f"\nMatch {i} (ID: {m.get('match_id', 'N/A')}):")
        log(f"  Team 1: {m['r1']:.2f} & {m['r2']:.2f} vs Team 2: {m['r3']:.2f} & {m['r4']:.2f}")
        log(f"  Score: {m['games1']}-{m['games2']}, Winner: Team {m['winner']}")
        log(f"  Expected games Team 1: {exp_g1:.2f}")
        log(f"  P1: actual={m['imp1']:.6f}, pred={imp1_p:.6f}, err={abs(m['imp1']-imp1_p):.6f}")
        log(f"  P2: actual={m['imp2']:.6f}, pred={imp2_p:.6f}, err={abs(m['imp2']-imp2_p):.6f}")
        log(f"  P3: actual={m['imp3']:.6f}, pred={imp3_p:.6f}, err={abs(m['imp3']-imp3_p):.6f}")
        log(f"  P4: actual={m['imp4']:.6f}, pred={imp4_p:.6f}, err={abs(m['imp4']-imp4_p):.6f}")
    
    # Save model
    model = {
        'K': float(K_fit),
        'scale': float(scale_fit),
        'mae': float(mae),
        'rmse': float(rmse),
        'n_train': len(train_data),
        'n_test': len(test_data),
        'formula': 'impact = K * (actual_games - expected_games) * sign',
    }
    with open('dupr_model.json', 'w') as f:
        json.dump(model, f, indent=2)
    
    log("\n" + "="*70)
    log("SUMMARY:")
    log(f"  Formula: impact = K * (actual_games - expected_games) * sign")
    log(f"  K = {K_fit:.8f}")
    log(f"  Expected games uses ELO with scale = {scale_fit:.2f}")
    log(f"  Test MAE: {mae:.8f} (average error per impact)")
    log(f"  Test RMSE: {rmse:.8f}")
    log("="*70)
    log("\nModel saved to dupr_model.json")
    
    # Write output file
    with open('fit_results.txt', 'w') as f:
        f.write('\n'.join(output_lines))

if __name__ == "__main__":
    main()
