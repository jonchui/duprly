#!/usr/bin/env python3
"""Simpler, faster DUPR model fit - outputs to fit_results.txt"""

import csv
import numpy as np
from scipy.optimize import minimize

def load_data(csv_path):
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
            except:
                continue
    return rows

def expected_games(r1, r2, r3, r4, scale=400):
    team1_avg = (r1 + r2) / 2
    team2_avg = (r3 + r4) / 2
    rating_diff = team1_avg - team2_avg
    prob_win = 1 / (1 + 10 ** (-rating_diff * scale / 400))
    return prob_win * 22  # Expected games for team 1

def predict_impacts(r1, r2, r3, r4, games1, games2, winner, K, scale):
    exp_g1 = expected_games(r1, r2, r3, r4, scale)
    result = games1 - exp_g1
    if winner == 1:
        return K * result * 0.5, K * result * 0.5, -K * result * 0.5, -K * result * 0.5
    else:
        return -K * result * 0.5, -K * result * 0.5, K * result * 0.5, K * result * 0.5

def loss(params, data):
    K, scale = params
    errors = []
    for m in data:
        imp1_p, imp2_p, imp3_p, imp4_p = predict_impacts(
            m['r1'], m['r2'], m['r3'], m['r4'],
            m['games1'], m['games2'], m['winner'], K, scale
        )
        errors.append((imp1_p - m['imp1'])**2)
        errors.append((imp2_p - m['imp2'])**2)
        errors.append((imp3_p - m['imp3'])**2)
        errors.append((imp4_p - m['imp4'])**2)
    return np.mean(errors)

with open('fit_results.txt', 'w') as out:
    out.write("="*60 + "\n")
    out.write("DUPR ALGORITHM REVERSE-ENGINEERING\n")
    out.write("="*60 + "\n\n")
    
    out.write("Loading data...\n")
    data = load_data('match_rating_data.csv')
    out.write(f"Loaded {len(data)} matches ({len(data)*4} impact observations)\n\n")
    
    split_idx = int(len(data) * 0.8)
    train, test = data[:split_idx], data[split_idx:]
    out.write(f"Train: {len(train)}, Test: {len(test)}\n\n")
    
    out.write("Fitting model...\n")
    result = minimize(loss, [0.01, 400], args=(train,), method='Nelder-Mead', options={'maxiter': 500})
    K, scale = result.x
    
    out.write(f"\nFITTED PARAMETERS:\n")
    out.write(f"  K (step size): {K:.8f}\n")
    out.write(f"  Scale (ELO): {scale:.2f}\n\n")
    
    # Test set evaluation
    test_errors = []
    for m in test[:100]:  # Sample first 100 for speed
        imp1_p, imp2_p, imp3_p, imp4_p = predict_impacts(
            m['r1'], m['r2'], m['r3'], m['r4'],
            m['games1'], m['games2'], m['winner'], K, scale
        )
        test_errors.extend([
            abs(imp1_p - m['imp1']), abs(imp2_p - m['imp2']),
            abs(imp3_p - m['imp3']), abs(imp4_p - m['imp4'])
        ])
    
    mae = np.mean(test_errors)
    out.write(f"TEST SET MAE (first 100 matches): {mae:.8f}\n\n")
    
    # Show examples
    out.write("EXAMPLE PREDICTIONS:\n")
    for i, m in enumerate(test[:5], 1):
        exp_g1 = expected_games(m['r1'], m['r2'], m['r3'], m['r4'], scale)
        imp1_p, imp2_p, imp3_p, imp4_p = predict_impacts(
            m['r1'], m['r2'], m['r3'], m['r4'],
            m['games1'], m['games2'], m['winner'], K, scale
        )
        out.write(f"\nMatch {i}:\n")
        out.write(f"  Ratings: {m['r1']:.2f} & {m['r2']:.2f} vs {m['r3']:.2f} & {m['r4']:.2f}\n")
        out.write(f"  Score: {m['games1']}-{m['games2']}, Winner: Team {m['winner']}\n")
        out.write(f"  Expected games Team 1: {exp_g1:.2f}\n")
        out.write(f"  P1: actual={m['imp1']:.6f}, pred={imp1_p:.6f}, err={abs(m['imp1']-imp1_p):.6f}\n")
        out.write(f"  P2: actual={m['imp2']:.6f}, pred={imp2_p:.6f}, err={abs(m['imp2']-imp2_p):.6f}\n")
        out.write(f"  P3: actual={m['imp3']:.6f}, pred={imp3_p:.6f}, err={abs(m['imp3']-imp3_p):.6f}\n")
        out.write(f"  P4: actual={m['imp4']:.6f}, pred={imp4_p:.6f}, err={abs(m['imp4']-imp4_p):.6f}\n")
    
    out.write("\n" + "="*60 + "\n")
    out.write("FORMULA:\n")
    out.write(f"  impact = K * (actual_games - expected_games) * sign\n")
    out.write(f"  where K = {K:.8f}\n")
    out.write(f"  and expected_games uses ELO with scale = {scale:.2f}\n")
    out.write("="*60 + "\n")

print("Fit complete. Results in fit_results.txt")
