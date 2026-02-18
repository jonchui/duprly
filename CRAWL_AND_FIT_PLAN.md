# Crawl 5000 Matches & Refit Model Plan

## What We've Set Up

### 1. Updated Crawl Script (`scripts/crawl_club_matches.py`)
- ✅ Fetches reliability for each player when crawling matches
- ✅ Stores reliability in `_crawl_metadata.reliability` in the JSON
- ✅ Commits to DB in batches of 50 matches
- ✅ Numbered logs for tracking progress
- ✅ Currently running: `python3 scripts/crawl_club_matches.py --max-matches 5000`

### 2. Updated Extract Script (`scripts/extract_match_rating_data.py`)
- ✅ Extracts reliability from `_crawl_metadata.reliability`
- ✅ Adds `rel1`, `rel2`, `rel3`, `rel4` columns to CSV
- ✅ Reports how many matches have reliability

### 3. New Fitting Script (`scripts/fit_dupr_with_reliability.py`)
- ✅ Fits model WITH reliability: `impact = K * (result_diff) * g(reliability)`
- ✅ Uses inverse reliability function: `g(rel) = a / (1 + rel/b)`
- ✅ Fits parameters: K, scale, a, b
- ✅ Evaluates on test set
- ✅ Saves updated model to `dupr_model.json`

### 4. New Validation Script (`scripts/validate_with_reliability.py`)
- ✅ Compares predictions WITH vs WITHOUT reliability
- ✅ Shows improvement metrics
- ✅ Reports correlation, MAE, RMSE improvements

### 5. Pipeline Script (`scripts/run_full_pipeline.sh`)
- ✅ Runs extract → fit → validate in sequence

## Current Status

**Crawl Running:** Background process crawling 5000 matches with reliability

**To Check Progress:**
```bash
tail -f crawl_5000_matches.log
# or
ps aux | grep crawl_club_matches
```

## Next Steps (After Crawl Completes)

1. **Extract matches with reliability:**
   ```bash
   python3 scripts/extract_match_rating_data.py
   ```

2. **Fit model with reliability:**
   ```bash
   python3 scripts/fit_dupr_with_reliability.py
   ```

3. **Validate improvements:**
   ```bash
   python3 scripts/validate_with_reliability.py
   ```

**Or run all at once:**
```bash
./scripts/run_full_pipeline.sh
```

## Expected Improvements

Once we refit with reliability, we should see:
- ✅ **Better correlation** (currently 0.048 is terrible)
- ✅ **Correct magnitude** (predictions currently 20x too small)
- ✅ **Better accuracy** for new vs established players

## Reliability Storage

Reliability is stored at **crawl time** (not match time) because:
- DUPR API doesn't provide historical reliability
- Crawl-time reliability ≈ match-time reliability for recent matches
- Better than nothing!

## Model Formula

**New formula:**
```
impact_i = K * (actual_games - expected_games) * sign * g(reliability_i)
```

Where:
- `g(reliability) = a / (1 + reliability/b)`
- Lower reliability → higher multiplier (new players move more)
- Parameters K, scale, a, b are all fitted together
