# Run when you're back

Everything is set up to get **1000 club matches** and have them ready for fitting the DUPR algorithm.

## What’s in place

- **DB:** Table `club_match_raw` in `dupr_db` stores full match JSON (pre-ratings + impacts).
- **Crawl:** `scripts/crawl_club_matches.py` — fetches club members’ match history, keeps only club matches, stops after 1000 with `--max-matches 1000`.
- **Extract:** `scripts/extract_match_rating_data.py` — reads `club_match_raw`, writes `match_rating_data.csv` (one row per match: r1..r4, imp1..imp4, games1, games2, winner).
- **One runner:** `run_crawl_1000.sh` — runs crawl then extract.

## Run it (one command)

From the repo root, with `.env` containing `DUPR_USERNAME`, `DUPR_PASSWORD`, `DUPR_CLUB_ID`:

```bash
chmod +x run_crawl_1000.sh
./run_crawl_1000.sh
```

When it finishes you’ll have:

- **~1000 rows** in `club_match_raw` (SQLite: `dupr.sqlite`)
- **match_rating_data.csv** with flattened rows for fitting

Then use `DUPR_ALGORITHM_README.md` to fit the model (e.g. in a notebook or `scripts/fit_dupr_model.py`). 1000 matches is enough for a first pass; run without `--max-matches` if you want every club match.
