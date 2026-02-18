#!/usr/bin/env python3
"""
Compare rating impact: 11-7 & 11-4 (22-11 total) vs a closer "last" match.
Run from repo root.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dupr_predictor import DuprPredictor

# Load predictor
p = DuprPredictor("dupr_model.json")

# Assume placeholder ratings (you can replace with real if known):
# You + partner (team 1) vs Michelle + Ryan (team 2)
# Using 4.0 vs 3.8 as example - adjust to your actual ratings
r1, r2 = 4.0, 4.0   # you and partner
r3, r4 = 3.8, 3.8   # Michelle & Ryan
rel = 50  # example reliability for all

# This match: won 11-7 and 11-4 → total 22-11
games1_this = 22
games2_this = 11
winner = 1  # you won

# "Last" match: assume closer, e.g. 11-9 and 11-8 → 22-17, or single game 11-7
games1_last = 11
games2_last = 7
# Or last was 21-19 style:
# games1_last = 21
# games2_last = 19

exp_this = p.expected_games(r1, r2, r3, r4)
exp_last = exp_this  # same opponents

imp_this = p.predict_impacts(r1, r2, r3, r4, games1_this, games2_this, winner, rel, rel, rel, rel)
imp_last = p.predict_impacts(r1, r2, r3, r4, games1_last, games2_last, winner, rel, rel, rel, rel)

# Your impact = first player on winning team (imp1)
your_impact_this = imp_this[0]
your_impact_last = imp_last[0]

print("Assumed: You+Partner 4.0/4.0 vs Michelle/Ryan 3.8/3.8, reliability 50")
print()
print("This match (11-7 and 11-4 → 22-11 total):")
print(f"  Expected games (you): {exp_this:.2f}")
print(f"  Result diff (actual - expected): {games1_this - exp_this:.2f}")
print(f"  Your predicted impact: {your_impact_this:+.4f}")
print()
print("Last match (e.g. 11-7 only, or 11-9+11-8 = 22-17):")
print(f"  Games you: {games1_last}, them: {games2_last}")
print(f"  Result diff: {games1_last - exp_last:.2f}")
print(f"  Your predicted impact: {your_impact_last:+.4f}")
print()
print("Comparison:")
print(f"  This match impact: {your_impact_this:+.4f}")
print(f"  Last match impact: {your_impact_last:+.4f}")
if your_impact_this > your_impact_last:
    print(f"  → Yes, this match (22-11) gets you more points than the last one.")
else:
    print(f"  → This match gets you the same or fewer points than the last one in this example.")
