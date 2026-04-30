"""
Tests for web.services.dupr_forecast using the Proxyman-captured DUPR
request/response fixtures in tests/fixtures/dupr_api/.

These tests run entirely offline — they force `use_fixtures=True` so
they never touch live DUPR. That means CI / local dev works without
DUPR_USERNAME / DUPR_PASSWORD.

Invariants (see tests/fixtures/dupr_api/README.md for the spec):

1. `winningRatingImpacts.length == winningScore` on `/forecast`.
2. `winProbabilityPercentage` sums to ~100 on `/forecast`; always null
   on `/expected-score`.
3. Under-dog: `rating_impacts[-1]` (tightest win) < `rating_impacts[0]`
   (blowout win). Blowouts move the rating more.
4. Favorite: `rating_impacts[0]` (blowout) <= 0 or least positive;
   `rating_impacts[-1]` (tight) is the biggest positive delta.

These all come directly from the real DUPR responses — if any break,
DUPR changed their API shape and we need to re-capture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from web.services import dupr_forecast as svc

# The 4 players in every captured fixture — keep tests deterministic.
TEAM_A = (4405492894, 7511597513)   # caller + partner (Jon chui + partner)
TEAM_B = (7270240621, 5651921565)   # opponents
TEAMS = [TEAM_A, TEAM_B]

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "dupr_api"


# ---- raw JSON sanity checks ----------------------------------------------

@pytest.mark.parametrize("name", sorted(p.name for p in FIXTURE_DIR.glob("*.json")))
def test_fixture_files_parse_as_json(name: str):
    with (FIXTURE_DIR / name).open() as f:
        data = json.load(f)
    assert "_meta" in data, f"{name} should carry a _meta block documenting the source"


# ---- expected-score semantics --------------------------------------------

@pytest.mark.parametrize("winning_score,expected_losing_score", [(11, 3.5), (15, 4.5)])
def test_expected_score_via_fixture(winning_score, expected_losing_score):
    mf = svc.expected_score(TEAMS, winning_score=winning_score, use_fixtures=True)
    assert mf.source == "fixture"
    assert mf.winning_score == winning_score

    # Exactly one team hits the winning_score, the other gets the fractional expected score.
    scores = sorted([mf.team_a.predicted_losing_score, mf.team_b.predicted_losing_score])
    assert scores == [expected_losing_score, float(winning_score)]

    # expected-score is the "slim" endpoint — no probabilities, no impacts.
    for t in (mf.team_a, mf.team_b):
        assert t.win_probability_pct is None
        assert t.rating_impacts == []


# ---- forecast semantics --------------------------------------------------

@pytest.mark.parametrize("winning_score", [11, 15])
def test_forecast_shape_via_fixture(winning_score):
    mf = svc.forecast(TEAMS, winning_score=winning_score, use_fixtures=True)
    assert mf.source == "fixture"

    # Invariant 1: impact arrays length == winning_score for BOTH teams.
    assert len(mf.team_a.rating_impacts) == winning_score
    assert len(mf.team_b.rating_impacts) == winning_score

    # Invariant 2: win probabilities sum to ~100.
    total = (mf.team_a.win_probability_pct or 0) + (mf.team_b.win_probability_pct or 0)
    assert 99 <= total <= 101, f"{winning_score}→{total}% (should sum to ~100)"


def test_forecast_underdog_favorite_directions():
    """Underdog's impacts should all be positive (a win lifts them).
    Favorite's impacts should start negative (blowout wins are neutral/negative)
    and climb as the loser scored more (a 'tight' win still gains them some)."""
    mf = svc.forecast(TEAMS, winning_score=11, use_fixtures=True)

    underdog, favorite = (
        (mf.team_a, mf.team_b)
        if (mf.team_a.win_probability_pct or 0) < (mf.team_b.win_probability_pct or 0)
        else (mf.team_b, mf.team_a)
    )

    # Underdog: every rating_impact is positive (beating the better team helps).
    assert all(x > 0 for x in underdog.rating_impacts), underdog.rating_impacts

    # Underdog blowout win (loser=0) > tight win (loser=10): bigger upset, bigger bump.
    assert underdog.rating_impacts[0] > underdog.rating_impacts[-1]

    # Favorite: impacts increase monotonically with loser score — closer games
    # are "more impressive" so they claw back more of the potential delta.
    for i in range(len(favorite.rating_impacts) - 1):
        assert favorite.rating_impacts[i] < favorite.rating_impacts[i + 1], (
            f"favorite impacts should be monotonically increasing: {favorite.rating_impacts}"
        )


def test_forecast_dataclass_helpers():
    mf = svc.forecast(TEAMS, winning_score=11, use_fixtures=True)
    assert mf.team_a.impact_if_blowout_win == mf.team_a.rating_impacts[0]
    assert mf.team_a.impact_if_tight_win == mf.team_a.rating_impacts[-1]


# ---- error handling ------------------------------------------------------

def test_forecast_unsupported_winning_score_without_live_creds(monkeypatch):
    """Any winning_score not covered by the fixture set + no live creds => 503."""
    monkeypatch.delenv("DUPR_USERNAME", raising=False)
    monkeypatch.delenv("DUPR_PASSWORD", raising=False)
    monkeypatch.setenv("DUPRLY_USE_FIXTURES", "1")  # force fixture path

    with pytest.raises(svc.DuprForecastUnavailable):
        svc.forecast(TEAMS, winning_score=21, use_fixtures=True)
