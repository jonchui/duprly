from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from .api_models import MatchDetail, SimilarityFactor

FEATURE_ORDER: Tuple[str, ...] = (
    "avg_team1_rating",
    "avg_team2_rating",
    "avg_team1_reliability",
    "avg_team2_reliability",
    "rating_diff",
    "margin",
    "is_tournament",
    "is_rec",
    "expected_points_for",
    "actual_points_for",
)

# Weights emphasize upset similarity: strong opponents, high reliability, big margin.
DEFAULT_WEIGHTS: Dict[str, float] = {
    "avg_team1_rating": 0.05,
    "avg_team2_rating": 0.20,
    "avg_team1_reliability": 0.05,
    "avg_team2_reliability": 0.15,
    "rating_diff": 0.20,
    "margin": 0.15,
    "is_tournament": 0.05,
    "is_rec": 0.05,
    "expected_points_for": 0.10,
    "actual_points_for": 0.05,
}


def _average(values: Iterable[Optional[float]]) -> Optional[float]:
    items = [v for v in values if v is not None]
    if not items:
        return None
    return sum(items) / len(items)


def _bool_to_float(value: bool) -> float:
    return 1.0 if value else 0.0


def _normalize_match_type(match_type: Optional[str]) -> str:
    if not match_type:
        return ""
    return match_type.strip().lower()


def build_feature_vector(
    match: MatchDetail,
    expected_points_for: Optional[float] = None,
) -> List[float]:
    team1 = [p for p in match.participants if p.side == 1]
    team2 = [p for p in match.participants if p.side == 2]

    avg_team1_rating = _average(p.doubles_rating for p in team1)
    avg_team2_rating = _average(p.doubles_rating for p in team2)
    avg_team1_rel = _average(p.reliability for p in team1)
    avg_team2_rel = _average(p.reliability for p in team2)

    rating_diff = None
    if avg_team1_rating is not None and avg_team2_rating is not None:
        rating_diff = avg_team1_rating - avg_team2_rating

    margin = None
    if match.score_for is not None and match.score_against is not None:
        margin = match.score_for - match.score_against

    match_type = _normalize_match_type(match.match_type)
    is_tournament = match_type in {"tournament", "league"} or "tournament" in match_type
    is_rec = match_type in {"rec", "recreation"} or "rec" in match_type

    actual_points_for = (
        float(match.score_for) if match.score_for is not None else None
    )

    values = {
        "avg_team1_rating": avg_team1_rating,
        "avg_team2_rating": avg_team2_rating,
        "avg_team1_reliability": avg_team1_rel,
        "avg_team2_reliability": avg_team2_rel,
        "rating_diff": rating_diff,
        "margin": margin,
        "is_tournament": _bool_to_float(is_tournament),
        "is_rec": _bool_to_float(is_rec),
        "expected_points_for": expected_points_for,
        "actual_points_for": actual_points_for,
    }

    return [float(values[name] or 0.0) for name in FEATURE_ORDER]


def weighted_distance(
    target: List[float],
    candidate: List[float],
    weights: Optional[Dict[str, float]] = None,
) -> float:
    if weights is None:
        weights = DEFAULT_WEIGHTS
    total = 0.0
    for idx, name in enumerate(FEATURE_ORDER):
        weight = weights.get(name, 0.0)
        total += weight * abs(target[idx] - candidate[idx])
    return total


def explain_similarity(
    target: List[float],
    candidate: List[float],
    weights: Optional[Dict[str, float]] = None,
) -> List[SimilarityFactor]:
    if weights is None:
        weights = DEFAULT_WEIGHTS
    factors: List[SimilarityFactor] = []
    for idx, name in enumerate(FEATURE_ORDER):
        weight = weights.get(name, 0.0)
        delta = target[idx] - candidate[idx]
        factors.append(
            SimilarityFactor(
                name=name,
                weight=weight,
                target=target[idx],
                actual=candidate[idx],
                delta=delta,
                explanation=f"Weighted delta for {name}.",
            )
        )
    return factors
