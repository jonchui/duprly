#!/usr/bin/env python3
"""Run DUPR fit - uses absolute paths"""

import csv
import json
import os
import numpy as np
from scipy.optimize import minimize

repo_path = os.getcwd()

print("="*70)
print("DUPR ALGORITHM REVERSE-ENGINEERING")
print(f"repo_path = {repo_path}")
print("="*70)
print(f"\nWorking directory: {os.getcwd()}")
print(f"CSV file exists: {os.path.exists('match_rating_data.csv')}\n")

print("Loading data...")
data = []
csv_path = os.path.join(repo_path, 'match_rating_data.csv')
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
            if len(data) < 5:  # Only print first few errors
                print(f"  Skipping row: {e}")
            continue

print(f"✓ Loaded {len(data)} matches ({len(data)*4} impact observations)\n")

def exp_games(r1, r2, r3, r4, scale=400):
    t1, t2 = (r1 + r2) / 2, (r3 + r4) / 2
    return (1 / (1 + 10 ** (-(t1 - t2) * scale / 400))) * 22

def pred(m, K, scale):
    exp = exp_games(m['r1'], m['r2'], m['r3'], m['r4'], scale)
    diff = m['games1'] - exp
    if m['winner'] == 1:
        return K * diff * 0.5, K * diff * 0.5, -K * diff * 0.5, -K * diff * 0.5
    return -K * diff * 0.5, -K * diff * 0.5, K * diff * 0.5, K * diff * 0.5

def loss(params, d):
    K, scale = params
    err = []
    for m in d:
        p1, p2, p3, p4 = pred(m, K, scale)
        err.extend([(p1-m['imp1'])**2, (p2-m['imp2'])**2, (p3-m['imp3'])**2, (p4-m['imp4'])**2])
    return np.mean(err)

train = data[:int(len(data)*0.8)]
test = data[int(len(data)*0.8):]
print(f"Train: {len(train)} matches, Test: {len(test)} matches")
print("Fitting model (this may take 30-60 seconds)...\n")

result = minimize(loss, [0.01, 400], args=(train,), method='Nelder-Mead', options={'maxiter': 500})
K, scale = result.x
print(f"✓ Fitted parameters:")
print(f"  K (step size): {K:.8f}")
print(f"  Scale (ELO): {scale:.2f}\n")

test_errs = []
for m in test:
    p1, p2, p3, p4 = pred(m, K, scale)
    test_errs.extend([abs(p1-m['imp1']), abs(p2-m['imp2']), abs(p3-m['imp3']), abs(p4-m['imp4'])])
mae = np.mean(test_errs)
print(f"Test MAE: {mae:.8f}\n")

# Save files
results_file = os.path.join(repo_path, 'fit_results.txt')
model_file = os.path.join(repo_path, 'dupr_model.json')

with open(model_file, 'w') as f:
    json.dump({'K': float(K), 'scale': float(scale), 'mae': float(mae)}, f, indent=2)

with open(results_file, 'w') as f:
    f.write(f"DUPR Model Fit Results\n{'='*50}\n")
    f.write(f"K (step size): {K:.8f}\n")
    f.write(f"Scale (ELO): {scale:.2f}\n")
    f.write(f"Test MAE: {mae:.8f}\n")
    f.write(f"\nFormula: impact = K * (actual_games - expected_games) * sign\n")
    f.write(f"Where expected_games uses ELO: prob = 1/(1+10^(-rating_diff*scale/400))\n")
    f.write(f"Expected games = prob * 22\n")

print("="*70)
print("RESULTS SAVED:")
print(f"  {results_file}")
print(f"  {model_file}")
print("="*70)
