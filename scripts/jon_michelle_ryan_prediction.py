#!/usr/bin/env python3
"""
Predict DUPR impact for Jon Chui's win vs Michelle & Ryan: 11-7 and 11-4.
Uses Jon's actual rating (3.857) and reliability (100).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dupr_predictor import DuprPredictor

p = DuprPredictor("dupr_model.json")

# Jon Chui (you): 3.857 doubles, reliability 100 (from DUPR)
# Annie Coyle (partner): 3.673 doubles, reliability 89 (lower = moves more per result)
# Michelle Baird & Ryan Makatura (from your recent match history)
r_jon = 3.857
r_partner = 3.673   # Annie Coyle
r_michelle = 3.749  # Michelle Baird
r_ryan = 3.571      # Ryan Makatura

rel_jon = 100
rel_partner = 89    # Annie - lower than you
rel_michelle = 100  # Michelle Baird
rel_ryan = 100      # Ryan Makatura

# Match: 11-7 and 11-4 → total 22-11 (you + partner = team 1)
games_us = 22
games_them = 11
winner = 1  # you won

exp_us = p.expected_games(r_jon, r_partner, r_michelle, r_ryan)
result_diff = games_us - exp_us

imp = p.predict_impacts(
    r_jon, r_partner, r_michelle, r_ryan,
    games_us, games_them, winner,
    rel_jon, rel_partner, rel_michelle, rel_ryan
)

print("=" * 60)
print("PREDICTION: Win vs Michelle & Ryan (11-7, 11-4)")
print("=" * 60)
print()
print("Ratings & reliability (from DUPR where looked up):")
print(f"  You (Jon):     {r_jon}  (reliability {rel_jon})")
print(f"  Partner (Annie): {r_partner}  (reliability {rel_partner} — lower, so she moves more)")
print(f"  Michelle Baird: {r_michelle}  (reliability {rel_michelle})")
print(f"  Ryan Makatura:  {r_ryan}  (reliability {rel_ryan})")
print()
print("Match result: 22-11 (two decisive games: 11-7 and 11-4)")
print()
print(f"Expected games for your team (in a 22-game match): {exp_us:.2f}")
print(f"Actual games you got: {games_us}")
print(f"Result diff (actual - expected): {result_diff:+.2f}")
print()
print("Predicted rating impacts:")
print(f"  You (Jon):     {imp[0]:+.4f}")
print(f"  Partner:       {imp[1]:+.4f}")
print(f"  Michelle:      {imp[2]:+.4f}")
print(f"  Ryan:          {imp[3]:+.4f}")
print()
print("=" * 60)
print("Summary")
print("=" * 60)
print(f"Your predicted gain: {imp[0]:+.4f} (e.g. 3.857 → ~{3.857 + imp[0]:.3f})")
print()
print("Why two decisive wins matter:")
print("  - Total margin 22-11 means you beat expectation by a lot.")
print("  - 11-7: solid win; 11-4: strong win → combined = big positive impact.")
print("  - Your reliability (100) means you're 'established' so moves are")
print("    slightly smaller than for a new player, but the margin still drives")
print("    a meaningful gain.")
print("=" * 60)
