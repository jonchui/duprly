# Reverse-Engineering the DUPR Rating Algorithm

We have enough data (pre-match ratings, post-match impacts, reliability, scores) to infer how DUPR turns match results into rating changes. This doc outlines the approach.

## Data We Have (per match)

From each club match JSON (`club_match_raw.raw_json`):

- **Inputs:**
  - **Pre-match ratings:** `teams[0].preMatchRatingAndImpact.preMatchDoubleRatingPlayer1/2`, same for `teams[1]`.
  - **Scores:** `teams[0].game1, game2, game3` vs `teams[1].game1, game2, game3` (or games to 11).
  - **Winner:** `teams[i].winner`.
  - **Reliability:** Not in the match payload; we can attach current reliability per player at crawl time (or from a separate lookup) for modeling.

- **Outputs (ground truth):**
  - **Impact per player:** `teams[i].preMatchRatingAndImpact.matchDoubleRatingImpactPlayer1/2` — the actual rating change DUPR applied.

So for every match we have: **4 pre-ratings, 4 impacts, 2 team scores (or games won), winner**. That’s enough to fit a model.

## Expected Score

DUPR’s `get_expected_score` returns expected points per team (e.g. 11 vs 9.5). We don’t have a closed-form formula, but we can:

1. **Approximate expected score** from the 4 pre-ratings, e.g. ELO-style:
   - Team strength = average of the two players’ ratings (or a weighted combo).
   - Expected games for team A = `f(r_A, r_B)` e.g. logistic: `1 / (1 + 10^((r_B - r_A) / scale))` scaled to a 0–22 (or 0–33) game total.
2. **Or** call the DUPR API for expected score using the 4 player IDs (but that uses *current* ratings, not pre-match; only valid if we run it at crawl time or accept drift).

For reverse-engineering, (1) is better: assume a simple formula for expected score from the 4 pre-ratings, then fit the scale and the impact formula.

## Impact Formula (to fit)

Plausible form (ELO-style):

- **Result:** “Actual” vs “expected” — e.g. `actual_games_A - expected_games_A` (or binary win/loss, or point differential).
- **Impact:**  
  `impact_i = K * (result_term) * g(reliability_i)`  
  where:
  - `K` is a global step size.
  - `result_term` might be `(actual - expected)` for the player’s team, or a logistic “surprise” term.
  - `g(reliability)` is larger for *lower* reliability (so new players move more). For example: `g(rel) = 1 / (1 + rel/100)` or `2 - rel/100` capped.

Per-player impact can be split (e.g. 50/50 within a team) or weighted by partner. We fit so that **predicted impact** matches **actual impact** in the DB.

## Pipeline

1. **Crawl**
   - Run: `python scripts/crawl_club_matches.py`
   - Optional: `--limit 100` for a test run, `--delay 0.3` to be nice to the API.
   - This fills `club_match_raw` with all club matches (with full JSON including pre/impact).

2. **Extract**
   - Script (or notebook) that:
     - Reads `club_match_raw`;
     - Parses each `raw_json`;
     - Extracts for each match: `(match_id, r1, r2, r3, r4, imp1, imp2, imp3, imp4, games1, games2, winner)`.
     - Optionally joins to player reliability (if we stored it at crawl time).
   - Output: CSV or a flattened table for modeling.

3. **Fit**
   - Define expected score = `expected_games(r1,r2,r3,r4)` (e.g. team avg + logistic).
   - Define impact model: `impact_i = K * (actual - expected)_i * g(rel_i)` (or similar).
   - Optimize K (and any scale/shape parameters) to minimize error between predicted and actual impacts (e.g. MSE or MAE over all 4 players across all matches).
   - Optionally fit separate K or g() for winning vs losing side.

4. **Validate**
   - Hold out 20% of matches (or last N by date); report MAE/MSE of predicted vs actual impact.
   - More matches → more accurate fit and more confidence in the nuances (reliability curve, win/loss asymmetry, etc.).

## Why More Matches Help

- **Stable estimates:** K and the reliability curve are estimated from many (match, player) impact observations. More matches ⇒ less noise.
- **Subgroup checks:** We can test if the same formula holds for high vs low reliability, or for big upsets vs expected results.
- **Edge cases:** Rare events (e.g. 11–0) appear more often in a large dataset, so we can see if DUPR caps or scales impacts differently.

## Quick Start

**One command (crawl 1000 matches + extract CSV):**
```bash
./run_crawl_1000.sh
```
Requires `.env` with `DUPR_USERNAME`, `DUPR_PASSWORD`, `DUPR_CLUB_ID`. Output: `match_rating_data.csv` and DB table `club_match_raw`.

**Or step by step:**
```bash
# 1. Ensure .env has DUPR_USERNAME, DUPR_PASSWORD, DUPR_CLUB_ID
# 2. Crawl up to 1000 club matches (stops when reached)
python scripts/crawl_club_matches.py --max-matches 1000 --delay 0.15

# 3. Extract to CSV for fitting
python scripts/extract_match_rating_data.py
```

**Is 1000 matches enough?** Yes for a first pass (4000 impact observations). More is better; run without `--max-matches` to get all club matches.

Then use `match_rating_data.csv` (or query `club_match_raw`) to fit and test the formula.
