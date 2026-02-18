#!/usr/bin/env python3
"""
Read club_match_raw and output a CSV with reliability data extracted from match JSON.
This checks if reliability is available in the fresh match data at match time.
Columns: match_id, event_date, r1..r4, rel1..rel4, imp1..imp4, games1, games2, winner.
Run from repo root. Output: match_rating_data_with_reliability.csv
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

def extract_reliability_from_player(player_data):
    """
    Extract reliability from player data in match JSON.
    Try multiple possible field names.
    """
    if not player_data:
        return None
    
    # Try different possible field names for reliability
    rel = (player_data.get("doublesReliabilityScore") or 
           player_data.get("doublesVerified") or
           player_data.get("reliability") or
           player_data.get("doublesReliability") or
           player_data.get("verified") or
           player_data.get("reliabilityScore"))
    
    if rel is not None:
        try:
            return int(rel)
        except (ValueError, TypeError):
            try:
                return float(rel)
            except (ValueError, TypeError):
                pass
    return None

def extract_reliability_from_match(data):
    """
    Extract reliability for all 4 players from match JSON.
    Check teams[].players[] and preMatchRatingAndImpact fields.
    """
    teams = data.get("teams", [])
    if len(teams) != 2:
        return None, None, None, None
    
    rels = [None, None, None, None]
    
    # Method 1: Check players array in teams
    for i, team in enumerate(teams):
        players = team.get("players", [])
        if len(players) >= 2:
            rel1 = extract_reliability_from_player(players[0])
            rel2 = extract_reliability_from_player(players[1])
            if i == 0:
                rels[0], rels[1] = rel1, rel2
            else:
                rels[2], rels[3] = rel1, rel2
    
    # Method 2: Check preMatchRatingAndImpact fields
    pre0 = teams[0].get("preMatchRatingAndImpact") or {}
    pre1 = teams[1].get("preMatchRatingAndImpact") or {}
    
    # Check if reliability is in preMatchRatingAndImpact
    for i, pre in enumerate([pre0, pre1]):
        # Try player1/player2 reliability fields
        rel_p1 = (pre.get("preMatchDoubleReliabilityPlayer1") or
                  pre.get("preMatchReliabilityPlayer1") or
                  pre.get("reliabilityPlayer1"))
        rel_p2 = (pre.get("preMatchDoubleReliabilityPlayer2") or
                  pre.get("preMatchReliabilityPlayer2") or
                  pre.get("reliabilityPlayer2"))
        
        if rel_p1 is not None or rel_p2 is not None:
            try:
                if i == 0:
                    if rel_p1 is not None:
                        rels[0] = int(rel_p1) if isinstance(rel_p1, (int, float)) else None
                    if rel_p2 is not None:
                        rels[1] = int(rel_p2) if isinstance(rel_p2, (int, float)) else None
                else:
                    if rel_p1 is not None:
                        rels[2] = int(rel_p1) if isinstance(rel_p1, (int, float)) else None
                    if rel_p2 is not None:
                        rels[3] = int(rel_p2) if isinstance(rel_p2, (int, float)) else None
            except (ValueError, TypeError):
                pass
    
    return rels[0], rels[1], rels[2], rels[3]

def main():
    eng = open_db()
    out_path = Path(__file__).resolve().parent.parent / "match_rating_data_with_reliability.csv"
    rows = []
    reliability_found_count = 0
    total_matches = 0
    
    print("Extracting match data with reliability...")
    with eng.connect() as conn:
        result = conn.execute(select(ClubMatchRaw))
        for r in result:
            total_matches += 1
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
            
            # Extract reliability
            rel1, rel2, rel3, rel4 = extract_reliability_from_match(data)
            
            if all(r is not None for r in [rel1, rel2, rel3, rel4]):
                reliability_found_count += 1
            
            g1 = games_from_team(t0)
            g2 = games_from_team(t1)
            winner = 1 if t0.get("winner") else 2
            rows.append({
                "match_id": r.match_id,
                "event_date": r.event_date or "",
                "r1": r1, "r2": r2, "r3": r3, "r4": r4,
                "rel1": rel1 if rel1 is not None else "",
                "rel2": rel2 if rel2 is not None else "",
                "rel3": rel3 if rel3 is not None else "",
                "rel4": rel4 if rel4 is not None else "",
                "imp1": i1, "imp2": i2, "imp3": i3, "imp4": i4,
                "games1": g1, "games2": g2,
                "winner": winner,
            })
    
    if not rows:
        print("No rows extracted. Run crawl_club_matches.py first.")
        return
    
    # Write CSV
    fieldnames = ["match_id", "event_date", "r1", "r2", "r3", "r4", 
                  "rel1", "rel2", "rel3", "rel4",
                  "imp1", "imp2", "imp3", "imp4", "games1", "games2", "winner"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    
    print(f"\nExtraction complete!")
    print(f"  Total matches processed: {total_matches}")
    print(f"  Matches with all 4 reliabilities: {reliability_found_count}")
    print(f"  Matches with partial reliability: {sum(1 for r in rows if any(r.get(f'rel{i}') for i in range(1,5)) and not all(r.get(f'rel{i}') for i in range(1,5)))}")
    print(f"  Wrote {len(rows)} rows to {out_path}")
    
    # Show sample of matches with reliability
    if reliability_found_count > 0:
        print(f"\nSample matches WITH reliability:")
        count = 0
        for row in rows:
            if all(row.get(f'rel{i}') for i in range(1,5)):
                print(f"  Match {row['match_id']}: rel1={row['rel1']}, rel2={row['rel2']}, rel3={row['rel3']}, rel4={row['rel4']}")
                count += 1
                if count >= 5:
                    break
    
    # Show sample match JSON structure for debugging
    if total_matches > 0 and reliability_found_count == 0:
        print(f"\n⚠️  No reliability found. Inspecting first match JSON structure...")
        with eng.connect() as conn:
            result = conn.execute(select(ClubMatchRaw).limit(1))
            for r in result:
                try:
                    data = json.loads(r.raw_json)
                    print("\nSample match JSON keys:")
                    print(f"  Top level: {list(data.keys())[:10]}")
                    if "teams" in data and len(data["teams"]) > 0:
                        team = data["teams"][0]
                        print(f"  Team keys: {list(team.keys())[:15]}")
                        if "players" in team and len(team["players"]) > 0:
                            player = team["players"][0]
                            print(f"  Player keys: {list(player.keys())[:20]}")
                        if "preMatchRatingAndImpact" in team:
                            pre = team["preMatchRatingAndImpact"]
                            print(f"  preMatchRatingAndImpact keys: {list(pre.keys())[:20]}")
                except Exception as e:
                    print(f"  Error inspecting JSON: {e}")

if __name__ == "__main__":
    main()
