#!/usr/bin/env python3
import csv, json, numpy as np
from scipy.optimize import minimize

# Load data
data = []
with open('match_rating_data.csv') as f:
    for r in csv.DictReader(f):
        try:
            data.append({
                'r1': float(r['r1']), 'r2': float(r['r2']),
                'r3': float(r['r3']), 'r4': float(r['r4']),
                'imp1': float(r['imp1']), 'imp2': float(r['imp2']),
                'imp3': float(r['imp3']), 'imp4': float(r['imp4']),
                'games1': int(r['games1']), 'games2': int(r['games2']),
                'winner': int(r['winner']),
            })
        except: pass

print(f"Loaded {len(data)} matches")

# Expected games function
def exp_games(r1, r2, r3, r4, scale=400):
    t1 = (r1 + r2) / 2
    t2 = (r3 + r4) / 2
    return (1 / (1 + 10 ** (-(t1 - t2) * scale / 400))) * 22

# Predict impacts
def pred(m, K, scale):
    exp = exp_games(m['r1'], m['r2'], m['r3'], m['r4'], scale)
    diff = m['games1'] - exp
    if m['winner'] == 1:
        return K * diff * 0.5, K * diff * 0.5, -K * diff * 0.5, -K * diff * 0.5
    return -K * diff * 0.5, -K * diff * 0.5, K * diff * 0.5, K * diff * 0.5

# Loss
def loss(params, d):
    K, scale = params
    err = []
    for m in d:
        p1, p2, p3, p4 = pred(m, K, scale)
        err.extend([(p1-m['imp1'])**2, (p2-m['imp2'])**2, (p3-m['imp3'])**2, (p4-m['imp4'])**2])
    return np.mean(err)

# Fit
train = data[:int(len(data)*0.8)]
test = data[int(len(data)*0.8):]
print(f"Fitting on {len(train)} train, {len(test)} test...")
result = minimize(loss, [0.01, 400], args=(train,), method='Nelder-Mead', options={'maxiter': 500})
K, scale = result.x
print(f"K={K:.8f}, scale={scale:.2f}")

# Evaluate
test_errs = []
for m in test:
    p1, p2, p3, p4 = pred(m, K, scale)
    test_errs.extend([abs(p1-m['imp1']), abs(p2-m['imp2']), abs(p3-m['imp3']), abs(p4-m['imp4'])])
mae = np.mean(test_errs)
print(f"Test MAE: {mae:.8f}")

# Save
with open('dupr_model.json', 'w') as f:
    json.dump({'K': float(K), 'scale': float(scale), 'mae': float(mae)}, f, indent=2)

with open('fit_results.txt', 'w') as f:
    f.write(f"DUPR Model Fit Results\n{'='*50}\n")
    f.write(f"K (step size): {K:.8f}\n")
    f.write(f"Scale (ELO): {scale:.2f}\n")
    f.write(f"Test MAE: {mae:.8f}\n")
    f.write(f"\nFormula: impact = K * (actual_games - expected_games) * sign\n")

print("Done! Results in fit_results.txt and dupr_model.json")
