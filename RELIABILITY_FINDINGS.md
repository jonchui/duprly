# Reliability Data Findings

## Test Results: Crawled 10 Fresh Matches

**Finding: Reliability is NOT included in the match JSON from `get_member_match_history_p`**

### What's in the Match JSON:
- ✅ Pre-match ratings (`preMatchDoubleRatingPlayer1/2`)
- ✅ Rating impacts (`matchDoubleRatingImpactPlayer1/2`)
- ✅ Match scores (`game1`, `game2`, `game3`)
- ✅ Winner information
- ❌ **Reliability is NOT in the match JSON**

### Where We Checked:
1. `teams[].preMatchRatingAndImpact` - ❌ No reliability fields
2. `teams[].player1/player2` objects - ❌ No reliability fields
3. Top-level match object - ❌ No reliability fields

### Player Object Structure:
```json
{
  "id": "...",
  "fullName": "...",
  "duprId": "...",
  "imageUrl": "...",
  "allowSubstitution": ...,
  "postMatchRating": ...,
  "validatedMatch": ...
}
```

## Solution: Fetch Reliability Separately

Since reliability is not in the match JSON, we need to:

1. **Option A: Fetch current reliability** (when crawling)
   - Use `get_player(duprId)` API call
   - Get `doublesReliabilityScore` or `doublesVerified` field
   - ⚠️ This gives CURRENT reliability, not historical reliability at match time

2. **Option B: Store reliability when crawling** (recommended)
   - When crawling matches, also fetch player data
   - Store reliability alongside match data
   - This captures reliability "at crawl time" (close to match time)

3. **Option C: Use average/estimated reliability**
   - If historical reliability isn't available, use current reliability
   - Or estimate based on number of matches played

## Next Steps

1. Update crawl script to fetch and store reliability when crawling matches
2. Update extract script to include reliability from stored player data
3. Refit model WITH reliability data

## Impact on Model

The model formula should be:
```
impact_i = K * (actual_games - expected_games) * g(reliability_i)
```

Where:
- `K` = global step size (fitted)
- `g(reliability)` = reliability multiplier function (fitted)
- Lower reliability → higher multiplier (new players move more)
