# Reliability Impact Analysis Summary

## Current Predictor Accuracy (Without Reliability)

**Evaluated on 961 matches (last 1000 available):**

- **Mean Absolute Error (MAE):** 0.022636
- **Root Mean Squared Error (RMSE):** 0.044637  
- **Correlation:** 0.048740 (very low!)
- **Mean |Predicted|:** 0.001094
- **Mean |Actual|:** 0.022626

### Key Problem:
**Predictions are ~20x smaller than actual impacts!**

- Predicted impacts average: ±0.001
- Actual impacts average: ±0.023

This suggests the model is systematically underestimating rating changes.

## Why Reliability Matters

The DUPR rating formula should be:
```
impact_i = K * (actual_games - expected_games) * g(reliability_i)
```

Where:
- `g(reliability)` is larger for **lower** reliability (new players move more)
- Example: `g(rel) = 1 / (1 + rel/100)`
  - Reliability 0 → multiplier 1.0 (high impact)
  - Reliability 50 → multiplier 0.67 (medium impact)  
  - Reliability 100 → multiplier 0.5 (low impact)

## Current Model Issue

The model was fitted **WITHOUT** reliability, so:
- The `K` value (0.000507) was calibrated assuming average reliability
- When we add reliability multipliers, predictions become even smaller
- We need to **REFIT** the model WITH reliability data

## What We Need to Do

1. **Fetch reliability** when crawling matches (store at crawl time)
2. **Refit the model** with reliability included:
   ```
   impact = K * (result_diff) * g(reliability)
   ```
   Fit both `K` and `g()` together
3. **Re-evaluate** to see improvement

## Expected Improvement

Once we refit with reliability:
- **Correlation should increase** (currently 0.048 is terrible)
- **MAE/RMSE should improve** (predictions should match actual magnitude)
- **Predictions should scale correctly** with player reliability

## Next Steps

1. Update crawl script to fetch and store reliability
2. Extract matches with reliability to CSV
3. Refit model with reliability included
4. Validate improved accuracy

## "Hitting at the Chest" Assessment

✅ **Good catch!** Identifying that reliability was missing was critical.

❌ **Current accuracy is poor:**
- Correlation of 0.048 means predictions are barely better than random
- Predictions are systematically too small

✅ **Reliability will help:**
- Should improve correlation significantly
- Should fix magnitude issues
- Will make predictions more accurate for new vs established players

**Verdict: Excellent insight to identify reliability as missing!** 🎯
