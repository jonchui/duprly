#!/usr/bin/env python3
"""
Deterministic sanity checks for shadow reset calculator.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dupr_predictor import DuprPredictor
from dupr_shadow_calculator import simulate_shadow_reset


def _build_sample_matches() -> list[dict]:
    # Newest first to mirror DUPR API history ordering.
    return [
        {
            "matchId": "m3",
            "eventDate": "2026-03-20T18:00:00Z",
            "teams": [
                {
                    "game1": 11,
                    "game2": 8,
                    "winner": True,
                    "player1": {
                        "id": "p1",
                        "ratings": {"doubles": 3.98, "doublesReliabilityScore": 95},
                    },
                    "player2": {
                        "id": "p2",
                        "ratings": {"doubles": 4.02, "doublesReliabilityScore": 96},
                    },
                    "preMatchRatingAndImpact": {
                        "preMatchDoubleRatingPlayer1": 3.98,
                        "preMatchDoubleRatingPlayer2": 4.02,
                    },
                },
                {
                    "game1": 9,
                    "game2": 6,
                    "winner": False,
                    "player1": {
                        "id": "p3",
                        "ratings": {"doubles": 4.05, "doublesReliabilityScore": 94},
                    },
                    "player2": {
                        "id": "p4",
                        "ratings": {"doubles": 4.01, "doublesReliabilityScore": 90},
                    },
                    "preMatchRatingAndImpact": {
                        "preMatchDoubleRatingPlayer1": 4.05,
                        "preMatchDoubleRatingPlayer2": 4.01,
                    },
                },
            ],
        },
        {
            "matchId": "m2",
            "eventDate": "2026-03-18T18:00:00Z",
            "teams": [
                {
                    "game1": 7,
                    "game2": 11,
                    "winner": False,
                    "players": [
                        {
                            "id": "p1",
                            "ratings": {"doubles": 3.94, "doublesReliabilityScore": 93},
                        },
                        {
                            "id": "p5",
                            "ratings": {"doubles": 4.08, "doublesReliabilityScore": 92},
                        },
                    ],
                    "preMatchRatingAndImpact": {
                        "preMatchDoubleRatingPlayer1": 3.94,
                        "preMatchDoubleRatingPlayer2": 4.08,
                    },
                },
                {
                    "game1": 11,
                    "game2": 8,
                    "winner": True,
                    "players": [
                        {
                            "id": "p6",
                            "ratings": {"doubles": 3.96, "doublesReliabilityScore": 91},
                        },
                        {
                            "id": "p7",
                            "ratings": {"doubles": 3.99, "doublesReliabilityScore": 89},
                        },
                    ],
                    "preMatchRatingAndImpact": {
                        "preMatchDoubleRatingPlayer1": 3.96,
                        "preMatchDoubleRatingPlayer2": 3.99,
                    },
                },
            ],
        },
        {
            "matchId": "m1",
            "eventDate": "2026-03-16T18:00:00Z",
            "teams": [
                {
                    "game1": 11,
                    "winner": True,
                    "player1": {
                        "id": "p8",
                        "ratings": {"doubles": 3.9, "doublesReliabilityScore": 85},
                    },
                    "player2": {
                        "id": "p9",
                        "ratings": {"doubles": 3.88, "doublesReliabilityScore": 88},
                    },
                    "preMatchRatingAndImpact": {
                        "preMatchDoubleRatingPlayer1": 3.9,
                        "preMatchDoubleRatingPlayer2": 3.88,
                    },
                },
                {
                    "game1": 6,
                    "winner": False,
                    "player1": {
                        "id": "p1",
                        "ratings": {"doubles": 3.9, "doublesReliabilityScore": 92},
                    },
                    "player2": {
                        "id": "p10",
                        "ratings": {"doubles": 4.02, "doublesReliabilityScore": 94},
                    },
                    "preMatchRatingAndImpact": {
                        "preMatchDoubleRatingPlayer1": 3.9,
                        "preMatchDoubleRatingPlayer2": 4.02,
                    },
                },
            ],
        },
    ]


def main() -> int:
    predictor = DuprPredictor("dupr_model.json")
    sample = _build_sample_matches()

    payload_a = simulate_shadow_reset(
        predictor=predictor,
        raw_matches=sample,
        player_id="p1",
        windows=[2, 3],
        mode="include_all",
        baseline_rating=4.0,
    )
    payload_b = simulate_shadow_reset(
        predictor=predictor,
        raw_matches=sample,
        player_id="p1",
        windows=[2, 3],
        mode="include_all",
        baseline_rating=4.0,
    )

    assert payload_a == payload_b, "Simulation output must be deterministic for same input."
    assert payload_a["results"]["2"]["matches_considered"] == 2
    assert payload_a["results"]["3"]["matches_considered"] == 3
    assert "shadow_rating" in payload_a["results"]["3"]

    threshold_payload = simulate_shadow_reset(
        predictor=predictor,
        raw_matches=sample,
        player_id="p1",
        windows=[3],
        mode="min_rel_threshold",
        min_rel=95.0,
        baseline_rating=4.0,
    )
    assert threshold_payload["results"]["3"]["matches_skipped"] >= 1

    weighted_payload = simulate_shadow_reset(
        predictor=predictor,
        raw_matches=sample,
        player_id="p1",
        windows=[3],
        mode="weighted_current",
        baseline_rating=4.0,
        current_reliability=90.0,
    )
    assert isinstance(weighted_payload["results"]["3"]["shadow_rating"], float)

    print("shadow reset sanity checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

