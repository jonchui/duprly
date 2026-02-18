# Pipeline Status

## Current Situation

### CSV Status
- ✅ `match_rating_data.csv` exists with 961 matches
- ❌ **No reliability columns** (`rel1`, `rel2`, `rel3`, `rel4`)
- This CSV was created before we added reliability fetching

### Crawl Status
- 🔄 Crawl script is running in background (fetching 5000 matches with reliability)
- Need to wait for crawl to complete, then extract

### Missing Dependencies
- ❌ `sqlalchemy` - needed for database access (extraction)
- ❌ `scipy` - needed for model fitting

## What Needs to Happen

### Option 1: Wait for Crawl + Install Dependencies
1. Wait for crawl to complete (check: `tail -f crawl_5000_matches.log`)
2. Install dependencies:
   ```bash
   pip3 install sqlalchemy scipy
   ```
3. Run pipeline:
   ```bash
   ./scripts/run_full_pipeline.sh
   ```

### Option 2: Use Existing CSV (No Reliability)
- Can fit model without reliability (but won't be accurate)
- Won't show improvement

### Option 3: Check Crawl Progress
```bash
# Check if crawl is still running
ps aux | grep crawl_club_matches

# Check crawl log
tail -f crawl_5000_matches.log

# Check how many matches in DB (if sqlalchemy available)
python3 -c "from dupr_db import open_db, ClubMatchRaw; from sqlalchemy import select; eng=open_db(); conn=eng.connect(); result=conn.execute(select(ClubMatchRaw)); print(f'Matches in DB: {len(list(result))}')"
```

## Next Steps

1. **Check crawl status** - is it still running?
2. **Install dependencies** - `pip3 install sqlalchemy scipy`
3. **Wait for crawl** - if still running, wait for it to finish
4. **Extract with reliability** - run extraction script
5. **Fit model** - run fitting script
6. **Validate** - run validation script

## Expected Timeline

- Crawl 5000 matches: ~30-60 minutes (fetching reliability takes time)
- Extract: ~1 minute
- Fit: ~1-2 minutes
- Validate: ~10 seconds

Total: ~35-65 minutes from crawl start
