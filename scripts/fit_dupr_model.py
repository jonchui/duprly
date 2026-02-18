#!/usr/bin/env python3
"""
Fit DUPR rating impact model from match_rating_data.csv.
Reverse-engineers: impact = K * (result_term) * f(reliability)

Since we don't have reliability in CSV, we'll:
1. Fit without reliability first (assume constant or average)
2. Optionally fetch reliability for players and refit
"""

import csv
import numpy as np
from scipy.optimize import minimize
from sklearn.metrics import mean_absolute_error, mean_squared_error
import json

def load_data(csv_path):
    """Load match data from CSV"""
    rows = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                rows.append({
                    'match_id': r['match_id'],
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
    """
    ELO-style expected score for team 1 (players r1, r2) vs team 2 (r3, r4).
    Returns expected games for team 1 (0-22 or 0-33 range).
    """
    team1_avg = (r1 + r2) / 2
    team2_avg = (r3 + r4) / 2
    rating_diff = team1_avg - team2_avg
    # Logistic probability that team1 wins
    prob_win = 1 / (1 + 10 ** (-rating_diff * scale / 400))
    # Expected games: if prob_win=0.5, expect ~11 games each (22 total)
    # Scale to typical match total (e.g. 22 games = 11-11 expected)
    total_games = 22  # Typical 2-game match
    expected_games1 = prob_win * total_games
    return expected_games1, prob_win

def predict_impact_simple(r1, r2, r3, r4, games1, games2, winner, K, scale=400):
    """
    Predict impact for each player using simple model:
    impact = K * (actual_games - expected_games) * sign(win)
    """
    expected_g1, prob_win = expected_score_elo(r1, r2, r3, r4, scale)
    actual_g1 = games1
    result_term = actual_g1 - expected_g1
    
    # Impact for team 1 players (positive if they won more than expected)
    if winner == 1:
        imp1_pred = K * result_term * 0.5  # Split between two players
        imp2_pred = K * result_term * 0.5
        imp3_pred = -K * result_term * 0.5  # Opposite for losers
        imp4_pred = -K * result_term * 0.5
    else:
        imp1_pred = -K * result_term * 0.5
        imp2_pred = -K * result_term * 0.5
        imp3_pred = K * result_term * 0.5
        imp4_pred = K * result_term * 0.5
    
    return imp1_pred, imp2_pred, imp3_pred, imp4_pred, expected_g1

def loss_function(params, data):
    """Loss: mean squared error between predicted and actual impacts"""
    K, scale = params
    total_error = 0
    count = 0
    for m in data:
        imp1_p, imp2_p, imp3_p, imp4_p, _ = predict_impact_simple(
            m['r1'], m['r2'], m['r3'], m['r4'],
            m['games1'], m['games2'], m['winner'], K, scale
        )
        total_error += (imp1_p - m['imp1'])**2
        total_error += (imp2_p - m['imp2'])**2
        total_error += (imp3_p - m['imp3'])**2
        total_error += (imp4_p - m['imp4'])**2
        count += 4
    return total_error / count if count > 0 else 1e10

def main():
    import sys
    # Write output to file as well as stdout
    log_file = open('fit_dupr_output.txt', 'w')
    def log(msg):
        print(msg)
        log_file.write(str(msg) + '\n')
        log_file.flush()
    
    log("Loading match data...")
    data = load_data('match_rating_data.csv')
    log(f"Loaded {len(data)} matches ({len(data)*4} impact observations)")
    
    # Split: 80% train, 20% test
    split_idx = int(len(data) * 0.8)
    train_data = data[:split_idx]
    test_data = data[split_idx:]
    log(f"Train: {len(train_data)} matches, Test: {len(test_data)} matches")
    
    # Initial guess: K=0.01, scale=400 (standard ELO)
    log("\nFitting model (K, scale)...")
    result = minimize(
        loss_function,
        x0=[0.01, 400],
        args=(train_data,),
        method='Nelder-Mead',
        options={'maxiter': 1000}
    )
    
    K_fit, scale_fit = result.x
    log(f"\nFitted parameters:")
    log(f"  K (step size): {K_fit:.6f}")
    log(f"  Scale (ELO): {scale_fit:.2f}")
    
    # Evaluate on test set
    log("\nEvaluating on test set...")
    test_preds = []
    test_actuals = []
    for m in test_data:
        imp1_p, imp2_p, imp3_p, imp4_p, exp_g1 = predict_impact_simple(
            m['r1'], m['r2'], m['r3'], m['r4'],
            m['games1'], m['games2'], m['winner'], K_fit, scale_fit
        )
        test_preds.extend([imp1_p, imp2_p, imp3_p, imp4_p])
        test_actuals.extend([m['imp1'], m['imp2'], m['imp3'], m['imp4']])
    
    mae = mean_absolute_error(test_actuals, test_preds)
    rmse = np.sqrt(mean_squared_error(test_actuals, test_preds))
    log(f"  MAE: {mae:.6f}")
    log(f"  RMSE: {rmse:.6f}")
    
    # Show some examples
    log("\nSample predictions (first 5 test matches):")
    for i, m in enumerate(test_data[:5], 1):
        imp1_p, imp2_p, imp3_p, imp4_p, exp_g1 = predict_impact_simple(
            m['r1'], m['r2'], m['r3'], m['r4'],
            m['games1'], m['games2'], m['winner'], K_fit, scale_fit
        )
        log(f"\nMatch {i} (ID: {m['match_id']}):")
        log(f"  Team 1: {m['r1']:.2f} & {m['r2']:.2f} vs Team 2: {m['r3']:.2f} & {m['r4']:.2f}")
        log(f"  Score: {m['games1']}-{m['games2']}, Winner: Team {m['winner']}")
        log(f"  Expected games Team 1: {exp_g1:.2f}")
        log(f"  Actual impacts:")
        log(f"    P1: {m['imp1']:.6f} (pred: {imp1_p:.6f}, err: {abs(m['imp1']-imp1_p):.6f})")
        log(f"    P2: {m['imp2']:.6f} (pred: {imp2_p:.6f}, err: {abs(m['imp2']-imp2_p):.6f})")
        log(f"    P3: {m['imp3']:.6f} (pred: {imp3_p:.6f}, err: {abs(m['imp3']-imp3_p):.6f})")
        log(f"    P4: {m['imp4']:.6f} (pred: {imp4_p:.6f}, err: {abs(m['imp4']-imp4_p):.6f})")
    
    # Save model
    model = {
        'K': float(K_fit),
        'scale': float(scale_fit),
        'mae': float(mae),
        'rmse': float(rmse),
        'n_train': len(train_data),
        'n_test': len(test_data),
    }
    with open('dupr_model.json', 'w') as f:
        json.dump(model, f, indent=2)
    log(f"\nModel saved to dupr_model.json")
    
    log("\n" + "="*60)
    log("SUMMARY:")
    log(f"  Formula: impact = K * (actual_games - expected_games) * sign")
    log(f"  K = {K_fit:.6f}")
    log(f"  Expected games uses ELO with scale = {scale_fit:.2f}")
    log(f"  Test MAE: {mae:.6f} (average error per impact)")
    log(f"  Test RMSE: {rmse:.6f}")
    log("="*60)
    log_file.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        with open('fit_error.txt', 'w') as f:
            import traceback
            f.write(f"Error: {e}\n")
            traceback.print_exc(f)
        raise
