"""
Forecast service.

Wraps the repo's fitted `DuprPredictor` (dupr_predictor.py + dupr_model.json)
and generates:

1) A single-match impact for a specific score.
2) A full "score matrix" — what every plausible final score would do to each
   player's rating.

The predictor itself is not re-derived here; we reuse the existing model.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional

# Make sure the repo root is importable when we're running under Vercel
# (api/index.py already adds it, but we keep this defensive for tests).
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from dupr_predictor import DuprPredictor  # noqa: E402


@lru_cache(maxsize=1)
def get_predictor() -> DuprPredictor:
    model_path = os.path.join(_REPO_ROOT, "dupr_model.json")
    return DuprPredictor(model_file=model_path)


@dataclass
class PlayerImpact:
    player: int  # 1..4
    pre_rating: float
    delta: float
    post_rating: float


@dataclass
class ForecastRow:
    games1: int
    games2: int
    winner: int
    expected_games_team1: float
    impacts: List[PlayerImpact]
    # Convenience summary deltas so the HTML table can render without nesting.
    d1: float
    d2: float
    d3: float
    d4: float


def _margin_aware_impacts(
    predictor: DuprPredictor,
    r1: float, r2: float, r3: float, r4: float,
    games1: int, games2: int, winner: int,
    rel1: Optional[float], rel2: Optional[float],
    rel3: Optional[float], rel4: Optional[float],
) -> tuple[float, float, float, float]:
    """
    A margin-sensitive version of predictor.predict_impacts().

    The fitted DuprPredictor's formula is:
        delta = K * (games1 - expected_g1) * 0.5 * reliability
    which depends *only* on the winner's game total (22) and completely ignores
    the loser's score. That means 22-0 and 22-18 produce the same delta —
    useless for a "pick a score" UX where the whole point is to see how a
    close 11-9 compares to an 11-0 blowout.

    We patch this locally by driving the K term off of **margin excess**
    (actual margin − expected margin, both as fractions of the total games
    played) instead of the raw winner total. That produces the expected
    monotonic behavior: bigger win vs expectation → bigger delta.

    See docs/TICKETS.md · T-001 for the underlying model gap — once the
    fitted predictor itself learns the losing-team term, this wrapper
    becomes redundant.
    """
    total = max(1, games1 + games2)
    # expected_games() returns expected games-won for team 1 assuming a
    # 22-total match. We rescale to the total of this specific match.
    expected_g1_frac = predictor.expected_games(r1, r2, r3, r4) / 22.0
    expected_margin = (2 * expected_g1_frac - 1) * total  # in games
    actual_margin = games1 - games2  # positive = team 1 won by this much
    margin_excess = actual_margin - expected_margin

    gR1 = predictor.reliability_multiplier(rel1)
    gR2 = predictor.reliability_multiplier(rel2)
    gR3 = predictor.reliability_multiplier(rel3)
    gR4 = predictor.reliability_multiplier(rel4)

    # K is fit on 22-total matches, so we don't divide by total again —
    # margin_excess is already in the same "games won vs expected" units.
    base = predictor.K * margin_excess * 0.5
    if winner == 1:
        return (base * gR1, base * gR2, -base * gR3, -base * gR4)
    else:
        return (base * gR1, base * gR2, -base * gR3, -base * gR4)


def forecast_one(
    r1: float,
    r2: float,
    r3: float,
    r4: float,
    games1: int,
    games2: int,
    rel1: Optional[float] = None,
    rel2: Optional[float] = None,
    rel3: Optional[float] = None,
    rel4: Optional[float] = None,
    margin_aware: bool = True,
) -> ForecastRow:
    """
    Forecast impact for a single concrete score.

    margin_aware: if True (default for the new score-picker UI), drives
        deltas off margin-vs-expected instead of winner-total-vs-expected.
        Set False for legacy behaviour (full score matrix was originally
        built around the fitted model's winner-only formula).
    """
    predictor = get_predictor()
    winner = 1 if games1 > games2 else 2
    expected = predictor.expected_games(r1, r2, r3, r4)
    if margin_aware:
        d1, d2, d3, d4 = _margin_aware_impacts(
            predictor, r1, r2, r3, r4, games1, games2, winner,
            rel1, rel2, rel3, rel4,
        )
    else:
        d1, d2, d3, d4 = predictor.predict_impacts(
            r1, r2, r3, r4, games1, games2, winner,
            rel1=rel1, rel2=rel2, rel3=rel3, rel4=rel4,
        )
    impacts = [
        PlayerImpact(1, r1, d1, r1 + d1),
        PlayerImpact(2, r2, d2, r2 + d2),
        PlayerImpact(3, r3, d3, r3 + d3),
        PlayerImpact(4, r4, d4, r4 + d4),
    ]
    return ForecastRow(
        games1=games1,
        games2=games2,
        winner=winner,
        expected_games_team1=expected,
        impacts=impacts,
        d1=d1, d2=d2, d3=d3, d4=d4,
    )


def _generate_candidate_scores(target: int = 22) -> List[tuple[int, int]]:
    """
    Generate every plausible *match-total* score.

    Important nuance: the fitted DuprPredictor was trained on match totals
    (sum of game-points across a best-of-3 match, e.g. an 11-7, 11-6 sweep
    becomes games1=22, games2=13), not single-game scores. See
    scripts/extract_match_rating_data.py where `games_from_team` sums
    game1+game2+game3.

    So we enumerate:
      - Team-1 sweeps: (22..30, 0..L) with L = winner - 2.
      - Team-1 2-1 splits: longer winner totals where both teams reached 11
        in at least two games.
      - Mirror for team 2.

    `target` here is the winner's *minimum* match-total (22 for 2 games to 11).
    """
    winner_totals = [target + i for i in (0, 1, 2, 3, 4, 6, 8, 11)]
    # Loser totals spaced to show interesting rating deltas; we clamp to
    # max = winner - 2 (win-by-2 rule at the match level is approximate).
    loser_totals_base = [0, 2, 5, 8, 10, 13, 15, 17, 18, 19, 20, 22, 24, 26]

    scores: List[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for w in winner_totals:
        for l in loser_totals_base + [w - 2]:
            if 0 <= l <= w - 2:
                pair = (w, l)
                if pair not in seen:
                    seen.add(pair)
                    scores.append(pair)
    # Mirror for team 2 wins.
    mirrored = []
    for (w, l) in scores:
        m = (l, w)
        if m not in seen:
            seen.add(m)
            mirrored.append(m)
    return scores + mirrored


def forecast_matrix(
    r1: float,
    r2: float,
    r3: float,
    r4: float,
    target: int = 22,
    rel1: Optional[float] = None,
    rel2: Optional[float] = None,
    rel3: Optional[float] = None,
    rel4: Optional[float] = None,
) -> List[ForecastRow]:
    """Run the predictor for every plausible final score and return sorted rows."""
    rows: List[ForecastRow] = []
    for g1, g2 in _generate_candidate_scores(target):
        rows.append(
            forecast_one(
                r1, r2, r3, r4, g1, g2,
                rel1=rel1, rel2=rel2, rel3=rel3, rel4=rel4,
            )
        )
    # Sort by team-1 score descending, then team-2 ascending — puts blowouts
    # first, matches intuition for "best to worst for team 1".
    rows.sort(key=lambda r: (-r.games1 + r.games2, -r.games1))
    return rows
