# Predictor Confidence: Jon Last-74 Evaluation

Run date: 2026-03-22

Command:

```bash
python3 scripts/evaluate_predictor_accuracy.py --limit 74
```

Determinism check:

```bash
python3 scripts/evaluate_predictor_accuracy.py --limit 74 --json > /tmp/eval74_run1.json
python3 scripts/evaluate_predictor_accuracy.py --limit 74 --json > /tmp/eval74_run2.json
shasum /tmp/eval74_run1.json /tmp/eval74_run2.json
```

Observed hash (both runs identical):

- `2e919f5edf3208a7060ddb61dcf7848713a04c6e`

## Coverage

- Requested limit: `74`
- Matches selected (usable with required pre/impact fields): `67`
- Reliability coverage (player-points): `168/268` (`62.69%`)
- Skipped rows:
  - missing required fields: `7`
  - non-Jon rows encountered while scanning table: `4666`

## Strict thresholds

- `R² >= 0.70`
- `Pearson >= 0.85`
- `MAE <= 0.020`

## Results

### Jon-only scorecard

- MAE: `0.033344`
- RMSE: `0.049558`
- Pearson: `-0.378144`
- Spearman: `-0.342007`
- R²: `-7.122069`
- Sign accuracy: `41.791%`
- Abs error p50/p90/p95: `0.018921 / 0.069746 / 0.113196`
- Strict status: `FAIL`

### All-player scorecard

- MAE: `0.042717`
- RMSE: `0.083070`
- Pearson: `-0.346205`
- Spearman: `-0.337105`
- R²: `-0.982663`
- Sign accuracy: `41.791%`
- Abs error p50/p90/p95: `0.022718 / 0.083752 / 0.128174`
- Strict status: `FAIL`

## Recommendation

- Overall strict pass: `NO`
- Practical trust level for reset what-if usage with this current model: `low_trust`
