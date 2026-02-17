#!/usr/bin/env python3
"""
Read club_match_raw and output a CSV with one row per match for fitting the DUPR model.
Columns: match_id, event_date, r1..r4 (pre ratings), imp1..imp4 (impacts), games1, games2, winner (1 or 2).
Run from repo root. Output: match_rating_data.csv
"""

import json
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dupr_db import open_db, ClubMatchRaw
from sqlalchemy import select

def games_from_team(team):
    g1, g2, g3 = team.get("game1") or 0, team.get("game2") or 0, team.get("game3") or 0
    total = 0
    for g in (g1, g2, g3):
        if g is not None and g >= 0:
            total += g
    return total

def main():
    eng = open_db()
    out_path = Path(__file__).resolve().parent.parent / "match_rating_data.csv"
    rows = []
    with eng.connect() as conn:
        result = conn.execute(select(ClubMatchRaw))
        for r in result:
            try:
                data = json.loads(r.raw_json)
            except Exception:
                continue
            teams = data.get("teams", [])
            if len(teams) != 2:
                continue
            t0, t1 = teams[0], teams[1]
            pre0 = t0.get("preMatchRatingAndImpact") or {}
            pre1 = t1.get("preMatchRatingAndImpact") or {}
            r1 = pre0.get("preMatchDoubleRatingPlayer1")
            r2 = pre0.get("preMatchDoubleRatingPlayer2")
            r3 = pre1.get("preMatchDoubleRatingPlayer1")
            r4 = pre1.get("preMatchDoubleRatingPlayer2")
            i1 = pre0.get("matchDoubleRatingImpactPlayer1")
            i2 = pre0.get("matchDoubleRatingImpactPlayer2")
            i3 = pre1.get("matchDoubleRatingImpactPlayer1")
            i4 = pre1.get("matchDoubleRatingImpactPlayer2")
            if None in (r1, r2, r3, r4, i1, i2, i3, i4):
                continue
            g1 = games_from_team(t0)
            g2 = games_from_team(t1)
            winner = 1 if t0.get("winner") else 2
            rows.append({
                "match_id": r.match_id,
                "event_date": r.event_date or "",
                "r1": r1, "r2": r2, "r3": r3, "r4": r4,
                "imp1": i1, "imp2": i2, "imp3": i3, "imp4": i4,
                "games1": g1, "games2": g2,
                "winner": winner,
            })
    if not rows:
        print("No rows extracted. Run crawl_club_matches.py first.")
        return
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out_path}")

if __name__ == "__main__":
    main()
