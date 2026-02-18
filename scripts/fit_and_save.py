#!/usr/bin/env python3
"""Fit DUPR model and save results - guaranteed file output"""

import csv
import json
import os
import numpy as np
from scipy.optimize import minimize
from pathlib import Path

# Ensure we're in the right directory
script_dir = Path(__file__).parent.parent
os.chdir(script_dir)

# Load data
print("Loading CSV...")
data = []
csv_path = script_dir / 'match_rating_data.csv'
with open(csv_path) as f:
    reader = csv.DictReader(f)
    for r in reader:
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
            print(f"Skipping row: {e}")
            continue

print(f"Loaded {len(data)} matches")

# Model functions
def exp_games(r1, r2, r3, r4, scale=400):
    t1 = (r1 + r2) / 2
    t2 = (r3 + r4) / 2
    prob = 1 / (1 + 10 ** (-(t1 - t2) * scale / 400))
    return prob * 22

def predict_impacts(m, K, scale):
    exp = exp_games(m['r1'], m['r2'], m['r3'], m['r4'], scale)
    diff = m['games1'] - exp
    if m['winner'] == 1:
        return K * diff * 0.5, K * diff * 0.5, -K * diff * 0.5, -K * diff * 0.5
    return -K * diff * 0.5, -K * diff * 0.5, K * diff * 0.5, K * diff * 0.5

def loss(params, d):
    K, scale = params
    errors = []
    for m in d:
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
train = data[:split_idx]
test = data[split_idx:]
print(f"Train: {len(train)}, Test: {len(test)}")

# Fit
print("Fitting model (this may take 30-60 seconds)...")
try:
    result = minimize(
        loss,
        [0.01, 400],
        args=(train,),
        method='Nelder-Mead',
        options={'maxiter': 500}
    )
    K, scale = result.x
    print(f"Fitted: K={K:.8f}, scale={scale:.2f}")
except Exception as e:
    print(f"Fitting failed: {e}")
    import traceback
    traceback.print_exc()
    K, scale = 0.01, 400  # Fallback

# Evaluate
print("Evaluating...")
test_errors = []
for m in test:
    p1, p2, p3, p4 = predict_impacts(m, K, scale)
    test_errors.extend([
        abs(p1 - m['imp1']),
        abs(p2 - m['imp2']),
        abs(p3 - m['imp3']),
        abs(p4 - m['imp4'])
    ])
mae = np.mean(test_errors)
rmse = np.sqrt(np.mean([e**2 for e in test_errors]))
print(f"Test MAE: {mae:.8f}, RMSE: {rmse:.8f}")

# Save results
results_file = script_dir / 'fit_results.txt'
model_file = script_dir / 'dupr_model.json'

with open(results_file, 'w') as f:
    f.write("="*70 + "\n")
    f.write("DUPR ALGORITHM REVERSE-ENGINEERING RESULTS\n")
    f.write("="*70 + "\n\n")
    f.write(f"Dataset: {len(data)} matches ({len(train)} train, {len(test)} test)\n\n")
    f.write("FITTED PARAMETERS:\n")
    f.write(f"  K (step size): {K:.8f}\n")
    f.write(f"  Scale (ELO): {scale:.2f}\n\n")
    f.write("ACCURACY:\n")
    f.write(f"  Test MAE: {mae:.8f}\n")
    f.write(f"  Test RMSE: {rmse:.8f}\n\n")
    f.write("FORMULA:\n")
    f.write("  impact = K * (actual_games - expected_games) * sign\n")
    f.write("  where:\n")
    f.write("    - expected_games uses ELO: prob = 1/(1+10^(-rating_diff*scale/400))\n")
    f.write("    - expected_games = prob * 22\n")
    f.write("    - sign = +0.5 for winners, -0.5 for losers\n")
    f.write("="*70 + "\n")

with open(model_file, 'w') as f:
    json.dump({
        'K': float(K),
        'scale': float(scale),
        'mae': float(mae),
        'rmse': float(rmse),
        'n_train': len(train),
        'n_test': len(test),
        'formula': 'impact = K * (actual_games - expected_games) * sign'
    }, f, indent=2)

print(f"\nResults saved to:")
print(f"  {results_file}")
print(f"  {model_file}")
