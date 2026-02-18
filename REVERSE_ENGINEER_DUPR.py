#!/usr/bin/env python3
"""
Reverse-engineer DUPR rating algorithm from match data.
Run: python3.11 REVERSE_ENGINEER_DUPR.py
"""

import csv
import json
import os
import numpy as np
from scipy.optimize import minimize
import sys
from pathlib import Path

# Ensure we're in repo root
repo_root = Path(__file__).parent
os.chdir(repo_root)

output_file = repo_root / 'DUPR_REVERSE_ENGINEERING_RESULTS.txt'
model_file = repo_root / 'dupr_model.json'

# Write header immediately
with open(output_file, 'w') as f:
    f.write("="*70 + "\n")
    f.write("DUPR ALGORITHM REVERSE-ENGINEERING\n")
    f.write("="*70 + "\n\n")
    f.flush()

def log(msg):
    print(msg)
    with open(output_file, 'a') as f:
        f.write(msg + "\n")
        f.flush()

log("Loading match data from match_rating_data.csv...")

data = []
csv_path = repo_root / 'match_rating_data.csv'
if not csv_path.exists():
    log(f"ERROR: {csv_path} not found!")
    sys.exit(1)

with open(csv_path) as f:
    reader = csv.DictReader(f)
    for i, r in enumerate(reader):
        try:
            data.append({
                'r1': float(r['r1']), 'r2': float(r['r2']),
                'r3': float(r['r3']), 'r4': float(r['r4']),
                'imp1': float(r['imp1']), 'imp2': float(r['imp2']),
                'imp3': float(r['imp3']), 'imp4': float(r['imp4']),
                'games1': int(r['games1']), 'games2': int(r['games2']),
                'winner': int(r['winner']),
            })
        except Exception as e:
            if i < 5:  # Only log first few errors
                log(f"  Skipping row {i}: {e}")
            continue

log(f"Loaded {len(data)} matches ({len(data)*4} impact observations)\n")

# Model: ELO-based expected score
def expected_games(r1, r2, r3, r4, scale=400):
    """Calculate expected games for team 1 using ELO formula"""
    team1_avg = (r1 + r2) / 2
    team2_avg = (r3 + r4) / 2
    rating_diff = team1_avg - team2_avg
    prob_win = 1 / (1 + 10 ** (-rating_diff * scale / 400))
    return prob_win * 22  # Typical match is ~22 total games

def predict_impacts(match, K, scale):
    """Predict rating impacts for all 4 players"""
    exp_g1 = expected_games(match['r1'], match['r2'], match['r3'], match['r4'], scale)
    actual_g1 = match['games1']
    result_diff = actual_g1 - exp_g1
    
    if match['winner'] == 1:
        # Team 1 won
        return (K * result_diff * 0.5, K * result_diff * 0.5,
                -K * result_diff * 0.5, -K * result_diff * 0.5)
    else:
        # Team 2 won
        return (-K * result_diff * 0.5, -K * result_diff * 0.5,
                K * result_diff * 0.5, K * result_diff * 0.5)

def loss_function(params, matches):
    """Mean squared error loss"""
    K, scale = params
    errors = []
    for m in matches:
        p1, p2, p3, p4 = predict_impacts(m, K, scale)
        errors.extend([
            (p1 - m['imp1'])**2,
            (p2 - m['imp2'])**2,
            (p3 - m['imp3'])**2,
            (p4 - m['imp4'])**2
        ])
    return np.mean(errors)

# Split data
split_idx = int(len(data) * 0.8)
train_data = data[:split_idx]
test_data = data[split_idx:]
log(f"Train set: {len(train_data)} matches")
log(f"Test set: {len(test_data)} matches\n")

# Fit model
log("Fitting model parameters (K, scale)...")
log("This may take 30-60 seconds...\n")

try:
    result = minimize(
        loss_function,
        x0=[0.01, 400],
        args=(train_data,),
        method='Nelder-Mead',
        options={'maxiter': 500}
    )
    K_fitted = result.x[0]
    scale_fitted = result.x[1]
    log(f"✓ Fitting complete!\n")
except Exception as e:
    log(f"ERROR during fitting: {e}")
    import traceback
    log(traceback.format_exc())
    K_fitted, scale_fitted = 0.01, 400

log("FITTED PARAMETERS:")
log(f"  K (step size): {K_fitted:.8f}")
log(f"  Scale (ELO): {scale_fitted:.2f}\n")

# Evaluate on test set
log("Evaluating on test set...")
test_errors = []
for m in test_data:
    p1, p2, p3, p4 = predict_impacts(m, K_fitted, scale_fitted)
    test_errors.extend([
        abs(p1 - m['imp1']),
        abs(p2 - m['imp2']),
        abs(p3 - m['imp3']),
        abs(p4 - m['imp4'])
    ])

mae = np.mean(test_errors)
rmse = np.sqrt(np.mean([e**2 for e in test_errors]))
log(f"  Mean Absolute Error (MAE): {mae:.8f}")
log(f"  Root Mean Squared Error (RMSE): {rmse:.8f}\n")

# Show examples
log("EXAMPLE PREDICTIONS (first 5 test matches):")
for i, m in enumerate(test_data[:5], 1):
    exp_g1 = expected_games(m['r1'], m['r2'], m['r3'], m['r4'], scale_fitted)
    p1, p2, p3, p4 = predict_impacts(m, K_fitted, scale_fitted)
    log(f"\nMatch {i}:")
    log(f"  Team 1: {m['r1']:.2f} & {m['r2']:.2f} vs Team 2: {m['r3']:.2f} & {m['r4']:.2f}")
    log(f"  Score: {m['games1']}-{m['games2']}, Winner: Team {m['winner']}")
    log(f"  Expected games Team 1: {exp_g1:.2f}")
    log(f"  P1: actual={m['imp1']:.6f}, pred={p1:.6f}, err={abs(m['imp1']-p1):.6f}")
    log(f"  P2: actual={m['imp2']:.6f}, pred={p2:.6f}, err={abs(m['imp2']-p2):.6f}")
    log(f"  P3: actual={m['imp3']:.6f}, pred={p3:.6f}, err={abs(m['imp3']-p3):.6f}")
    log(f"  P4: actual={m['imp4']:.6f}, pred={p4:.6f}, err={abs(m['imp4']-p4):.6f}")

# Save model JSON
model_data = {
    'K': float(K_fitted),
    'scale': float(scale_fitted),
    'mae': float(mae),
    'rmse': float(rmse),
    'n_train': len(train_data),
    'n_test': len(test_data),
    'formula': 'impact = K * (actual_games - expected_games) * sign'
}

with open(model_file, 'w') as f:
    json.dump(model_data, f, indent=2)

log("\n" + "="*70)
log("SUMMARY:")
log(f"  Formula: impact = K * (actual_games - expected_games) * sign")
log(f"  K = {K_fitted:.8f}")
log(f"  Expected games uses ELO with scale = {scale_fitted:.2f}")
log(f"  Test MAE: {mae:.8f} (average error per impact)")
log(f"  Test RMSE: {rmse:.8f}")
log("="*70)
log(f"\nResults saved to:")
log(f"  {output_file}")
log(f"  {model_file}")
