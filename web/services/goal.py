"""
Reverse-forecast — "what do I have to win?"

Given:
  - me_slot: which player slot (1..4) I am
  - r1..r4: pre-match ratings for all 4 players
  - target_delta: e.g. +0.050 (I want to gain 5 points)
  - goal_direction: "gain" or "lose" (defaults to "gain" when target_delta > 0)
  - (optional) reliability values

Produces:
  - `rows`: every plausible final score + my delta + whether the score hits my goal
  - `best_case`: the single score that maximally helps me
  - `worst_case`: the single score that maximally hurts me
  - `hits_goal`: whether my goal is *achievable at all* in a single match with
    these opponents (i.e. best_case.delta >= target_delta)
  - `winning_scores_that_hit_goal`: filtered list of scores that get me there

This is the core of the "I need +0.05 — what do I have to do in this
tournament?" feature. For the MVP we focus on a single match; multi-match
tournament planning comes next.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from web.services.forecast import ForecastRow, forecast_matrix


@dataclass
class GoalRow:
    games1: int
    games2: int
    winner: int
    my_delta: float
    my_post_rating: float
    hits_goal: bool
    gap_to_goal: float  # my_delta - target_delta; positive means surplus


@dataclass
class GoalForecast:
    me_slot: int
    my_pre_rating: float
    target_delta: float
    best_case_delta: float
    worst_case_delta: float
    hits_goal: bool
    best_score: Optional[str]
    worst_score: Optional[str]
    rows: List[GoalRow]

    def rows_that_hit(self) -> List[GoalRow]:
        return [r for r in self.rows if r.hits_goal]


def _pick_delta(row: ForecastRow, slot: int) -> float:
    return row.impacts[slot - 1].delta


def compute(
    me_slot: int,
    r1: float, r2: float, r3: float, r4: float,
    target_delta: float,
    target: int = 22,
    rel1: Optional[float] = None,
    rel2: Optional[float] = None,
    rel3: Optional[float] = None,
    rel4: Optional[float] = None,
) -> GoalForecast:
    if me_slot not in (1, 2, 3, 4):
        raise ValueError("me_slot must be 1, 2, 3, or 4")

    matrix = forecast_matrix(
        r1, r2, r3, r4, target=target,
        rel1=rel1, rel2=rel2, rel3=rel3, rel4=rel4,
    )
    my_pre = (r1, r2, r3, r4)[me_slot - 1]

    goal_rows: List[GoalRow] = []
    best_delta = float("-inf")
    worst_delta = float("inf")
    best_row: Optional[ForecastRow] = None
    worst_row: Optional[ForecastRow] = None

    for row in matrix:
        d = _pick_delta(row, me_slot)
        hits = d >= target_delta if target_delta >= 0 else d <= target_delta
        goal_rows.append(
            GoalRow(
                games1=row.games1,
                games2=row.games2,
                winner=row.winner,
                my_delta=d,
                my_post_rating=my_pre + d,
                hits_goal=hits,
                gap_to_goal=d - target_delta,
            )
        )
        if d > best_delta:
            best_delta = d
            best_row = row
        if d < worst_delta:
            worst_delta = d
            worst_row = row

    # Sort rows so the goal-hitting ones come first, then by gap_to_goal desc
    # — makes the UI table show "easiest way to hit my goal" at the top.
    goal_rows.sort(key=lambda r: (not r.hits_goal, -r.gap_to_goal))

    return GoalForecast(
        me_slot=me_slot,
        my_pre_rating=my_pre,
        target_delta=target_delta,
        best_case_delta=best_delta if best_row else 0.0,
        worst_case_delta=worst_delta if worst_row else 0.0,
        hits_goal=(best_delta >= target_delta) if target_delta >= 0 else (worst_delta <= target_delta),
        best_score=f"{best_row.games1}-{best_row.games2}" if best_row else None,
        worst_score=f"{worst_row.games1}-{worst_row.games2}" if worst_row else None,
        rows=goal_rows,
    )
