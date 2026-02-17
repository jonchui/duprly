#!/bin/bash
# Run from repo root. Crawl 1000 club matches then extract CSV.
# Requires: .env with DUPR_USERNAME, DUPR_PASSWORD, DUPR_CLUB_ID

set -e
cd "$(dirname "$0")"
echo "Crawling club matches (max 1000)..."
python3.11 scripts/crawl_club_matches.py --max-matches 1000 --delay 0.15
echo "Extracting rating data to CSV..."
python3.11 scripts/extract_match_rating_data.py
echo "Done. See match_rating_data.csv and DUPR_ALGORITHM_README.md"
