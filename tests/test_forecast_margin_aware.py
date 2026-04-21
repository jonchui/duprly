"""
Tests for the margin-aware forecast used by the /forecast/card score picker.

Key invariant the old fitted-model path violated (T-001): deltas must vary
with the losing team's score. The score picker on /forecast is essentially
unusable if 11-0, 11-7, and 11-9 all produce the same rating change.

We also cover the /forecast/card HTTP route so the UI contract is tested
end-to-end.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from web.main import app
from web.services.forecast import forecast_one


# Team 2 is the slight favorite (3.85 + 4.41 > 3.86 + 4.07).
R1, R2, R3, R4 = 3.86, 4.07, 3.85, 4.41


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


class TestMarginAwareOne:
    def test_deltas_strictly_decrease_as_win_narrows(self):
        """11-0 > 11-4 > 11-7 > 11-9 deltas must be monotonically decreasing."""
        deltas = [forecast_one(R1, R2, R3, R4, 11 * 2, l * 2).d1 for l in [0, 4, 7, 9]]
        for prev, nxt in zip(deltas, deltas[1:]):
            assert prev > nxt, f"expected monotone decrease, got {deltas}"

    def test_loss_deltas_strictly_decrease_in_severity(self):
        """Team-1 loss deltas: 9-11 closer-to-zero than 0-11 blowout loss."""
        narrow_loss = forecast_one(R1, R2, R3, R4, 9 * 2, 11 * 2).d1
        blowout_loss = forecast_one(R1, R2, R3, R4, 0 * 2, 11 * 2).d1
        assert narrow_loss > blowout_loss
        assert blowout_loss < 0

    def test_team_symmetry(self):
        """Team-1's delta for (g1,g2) equals −team-2's delta at same score."""
        row = forecast_one(R1, R2, R3, R4, 22, 14)
        assert row.d1 == pytest.approx(-row.d3, abs=1e-9)
        assert row.d2 == pytest.approx(-row.d4, abs=1e-9)

    def test_legacy_mode_matches_old_predictor(self):
        """margin_aware=False preserves the original fitted-model behavior."""
        a = forecast_one(R1, R2, R3, R4, 22, 0, margin_aware=False).d1
        b = forecast_one(R1, R2, R3, R4, 22, 18, margin_aware=False).d1
        assert a == pytest.approx(b, abs=1e-9), (
            "legacy predictor was fitted on winner-total only; these two scores "
            "should return the same delta (documents T-001 model gap)"
        )

    def test_upset_loss_can_be_positive(self):
        """
        Losing narrowly to a stronger team can net a *positive* delta — the
        system rewarded team 1 for beating expectations. This is Elo/DUPR
        canon. If this breaks, the margin-aware term is wrong-signed.
        """
        # Team 2 is favored; team 1 loses 22-20 (a narrow 11-10 sweep loss).
        row = forecast_one(R1, R2, R3, R4, 20, 22)
        assert row.d1 > 0, f"expected upset-loss to be positive, got {row.d1:+.4f}"


class TestForecastCardRoute:
    def test_card_html_contains_score_and_names(self, client: TestClient):
        r = client.get(
            "/forecast/card",
            params={
                "r1": R1, "r2": R2, "r3": R3, "r4": R4,
                "games1": 11, "games2": 7,
                "name1": "Jon Chui", "name2": "Harrison Webb",
                "name3": "Cody F", "name4": "Erich Wagner",
            },
        )
        assert r.status_code == 200
        body = r.text
        assert "Jon Chui" in body
        assert "Harrison Webb" in body
        assert "11-7" in body  # rendered in the "Score preview · 11-7 · 2-0 sweep"
        # Team 1 wins → emerald (win) styling somewhere in the body.
        assert "emerald" in body
        assert "rose" in body  # team 2 cards are styled as loss.

    def test_card_rejects_ties(self, client: TestClient):
        r = client.get(
            "/forecast/card",
            params={"r1": R1, "r2": R2, "r3": R3, "r4": R4, "games1": 11, "games2": 11},
        )
        assert r.status_code == 200
        assert "aren't rated" in r.text.lower() or "tie" in r.text.lower()

    def test_card_three_game_split_has_different_delta_than_sweep(self, client: TestClient):
        """A 2-1 split vs a 2-0 sweep for the same single-game score should differ."""
        sweep = client.get(
            "/forecast/card",
            params={
                "r1": R1, "r2": R2, "r3": R3, "r4": R4,
                "games1": 11, "games2": 9, "games_played": 2,
            },
        ).text
        split = client.get(
            "/forecast/card",
            params={
                "r1": R1, "r2": R2, "r3": R3, "r4": R4,
                "games1": 11, "games2": 9, "games_played": 3,
            },
        ).text
        assert "2-0 sweep" in sweep
        assert "2-1 split" in split
