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
) -> ForecastRow:
    """Forecast impact for a single concrete score."""
    predictor = get_predictor()
    winner = 1 if games1 > games2 else 2
    expected = predictor.expected_games(r1, r2, r3, r4)
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


def _generate_candidate_scores(target: int = 11) -> List[tuple[int, int]]:
    """
    Generate every plausible final score for a win-by-2 game to `target`.

    For target=11 we emit:
      Team1 wins: 11-0 .. 11-9, then 12-10, 13-11, 14-12, 15-13 (cap the tail)
      Team2 wins: mirror
    """
    scores: List[tuple[int, int]] = []
    for losing in range(0, target - 1):  # 0..9 for target=11
        scores.append((target, losing))
    # Win-by-2 tail up to target+4
    for winning in range(target + 1, target + 5):
        scores.append((winning, winning - 2))
    mirrored = [(b, a) for (a, b) in scores]
    return scores + mirrored


def forecast_matrix(
    r1: float,
    r2: float,
    r3: float,
    r4: float,
    target: int = 11,
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
