#!/bin/bash
# Full pipeline: Extract -> Fit -> Validate

set -e

echo "=========================================="
echo "DUPR MODEL PIPELINE WITH RELIABILITY"
echo "=========================================="
echo ""

echo "[STEP 1] Extracting match data with reliability..."
if python3 -c "import sqlalchemy" 2>/dev/null; then
    python3 scripts/extract_match_rating_data.py
else
    echo "  ⚠️  sqlalchemy not available - skipping extraction"
    echo "  Using existing match_rating_data.csv if available"
    if [ ! -f match_rating_data.csv ]; then
        echo "  ❌ No CSV file found! Cannot continue."
        exit 1
    fi
fi

echo ""
echo "[STEP 2] Fitting model with reliability..."
python3 scripts/fit_dupr_with_reliability.py

echo ""
echo "[STEP 3] Validating predictor..."
python3 scripts/validate_with_reliability.py

echo ""
echo "=========================================="
echo "PIPELINE COMPLETE!"
echo "=========================================="
