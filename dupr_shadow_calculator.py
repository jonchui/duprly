#!/usr/bin/env python3
"""
Shadow reset calculator for rolling last-N DUPR match windows.

This module replays match impacts for a single player across a recent match
window (for example 8/16/24 matches) using the reverse-engineered predictor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from dupr_predictor import DuprPredictor


RELIABILITY_KEYS = (
    "doublesReliabilityScore",
    "doublesVerified",
    "reliability",
    "doublesReliability",
    "reliabilityScore",
    "verified",
)

RATING_KEYS = ("doubles", "doublesRating", "doubles_rating")
DATE_KEYS = ("eventDate", "event_date", "matchDate", "date")
MATCH_ID_KEYS = ("matchId", "match_id", "id")


@dataclass
class NormalizedMatch:
    match_id: str
    event_date: Optional[datetime]
    r1: float
    r2: float
    r3: float
    r4: float
    games1: int
    games2: int
    winner: int
    rel1: Optional[float]
    rel2: Optional[float]
    rel3: Optional[float]
    rel4: Optional[float]
    slot: int
    target_pre_rating: float
    target_reliability: Optional[float]
    partner_id: Optional[str]
    opponent_ids: Tuple[Optional[str], Optional[str]]


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_event_date(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            dt = datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _extract_first(d: Dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in d and d[key] is not None:
            return d[key]
    return None


def _extract_player_id(player: Dict[str, Any]) -> Optional[str]:
    if not isinstance(player, dict):
        return None
    raw = (
        player.get("id")
        or player.get("playerId")
        or player.get("userId")
        or player.get("duprId")
    )
    if raw is None:
        return None
    return str(raw)


def _extract_player_reliability(player: Dict[str, Any]) -> Optional[float]:
    if not isinstance(player, dict):
        return None
    for key in RELIABILITY_KEYS:
        val = _safe_float(player.get(key))
        if val is not None:
            return val
    ratings = player.get("ratings")
    if isinstance(ratings, dict):
        for key in RELIABILITY_KEYS:
            val = _safe_float(ratings.get(key))
            if val is not None:
                return val
    return None


def _extract_player_doubles_rating(player: Dict[str, Any]) -> Optional[float]:
    if not isinstance(player, dict):
        return None
    for key in RATING_KEYS:
        val = _safe_float(player.get(key))
        if val is not None:
            return val
    ratings = player.get("ratings")
    if isinstance(ratings, dict):
        for key in RATING_KEYS:
            val = _safe_float(ratings.get(key))
            if val is not None:
                return val
    return None


def _extract_team_players(team: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    player1 = team.get("player1") if isinstance(team.get("player1"), dict) else None
    player2 = team.get("player2") if isinstance(team.get("player2"), dict) else None
    if player1 and player2:
        return player1, player2

    players = team.get("players")
    if isinstance(players, list) and len(players) >= 2:
        p1 = players[0] if isinstance(players[0], dict) else {}
        p2 = players[1] if isinstance(players[1], dict) else {}
        return p1, p2

    return player1 or {}, player2 or {}


def _games_from_team(team: Dict[str, Any]) -> int:
    game_keys = ("game1", "game2", "game3")
    games = [_safe_int(team.get(k)) for k in game_keys]
    values = [g for g in games if g is not None and g >= 0]
    if values:
        return int(sum(values))
    score = _safe_int(team.get("score"))
    return score if score is not None else 0


def _extract_match_id(match: Dict[str, Any], idx: int) -> str:
    raw = _extract_first(match, MATCH_ID_KEYS)
    return str(raw) if raw is not None else f"match-{idx}"


def _extract_date(match: Dict[str, Any]) -> Optional[datetime]:
    for key in DATE_KEYS:
        dt = _parse_event_date(match.get(key))
        if dt is not None:
            return dt
    return None


def normalize_match_for_player(
    match: Dict[str, Any], player_id: str, idx: int
) -> Optional[NormalizedMatch]:
    teams = match.get("teams")
    if not isinstance(teams, list) or len(teams) != 2:
        return None
    team0 = teams[0] if isinstance(teams[0], dict) else {}
    team1 = teams[1] if isinstance(teams[1], dict) else {}

    t0p1, t0p2 = _extract_team_players(team0)
    t1p1, t1p2 = _extract_team_players(team1)

    t0p1_id = _extract_player_id(t0p1)
    t0p2_id = _extract_player_id(t0p2)
    t1p1_id = _extract_player_id(t1p1)
    t1p2_id = _extract_player_id(t1p2)
    all_ids = [t0p1_id, t0p2_id, t1p1_id, t1p2_id]

    player_id_str = str(player_id)
    if player_id_str not in [pid for pid in all_ids if pid is not None]:
        return None

    pre0 = team0.get("preMatchRatingAndImpact") if isinstance(team0.get("preMatchRatingAndImpact"), dict) else {}
    pre1 = team1.get("preMatchRatingAndImpact") if isinstance(team1.get("preMatchRatingAndImpact"), dict) else {}

    r1 = _safe_float(pre0.get("preMatchDoubleRatingPlayer1")) or _extract_player_doubles_rating(t0p1)
    r2 = _safe_float(pre0.get("preMatchDoubleRatingPlayer2")) or _extract_player_doubles_rating(t0p2)
    r3 = _safe_float(pre1.get("preMatchDoubleRatingPlayer1")) or _extract_player_doubles_rating(t1p1)
    r4 = _safe_float(pre1.get("preMatchDoubleRatingPlayer2")) or _extract_player_doubles_rating(t1p2)
    if None in (r1, r2, r3, r4):
        return None

    rel1 = _extract_player_reliability(t0p1)
    rel2 = _extract_player_reliability(t0p2)
    rel3 = _extract_player_reliability(t1p1)
    rel4 = _extract_player_reliability(t1p2)

    g1 = _games_from_team(team0)
    g2 = _games_from_team(team1)
    winner = 1 if bool(team0.get("winner")) else 2

    if t0p1_id == player_id_str:
        slot = 1
        partner_id = t0p2_id
        opponent_ids = (t1p1_id, t1p2_id)
        target_pre = r1
        target_rel = rel1
    elif t0p2_id == player_id_str:
        slot = 2
        partner_id = t0p1_id
        opponent_ids = (t1p1_id, t1p2_id)
        target_pre = r2
        target_rel = rel2
    elif t1p1_id == player_id_str:
        slot = 3
        partner_id = t1p2_id
        opponent_ids = (t0p1_id, t0p2_id)
        target_pre = r3
        target_rel = rel3
    else:
        slot = 4
        partner_id = t1p1_id
        opponent_ids = (t0p1_id, t0p2_id)
        target_pre = r4
        target_rel = rel4

    return NormalizedMatch(
        match_id=_extract_match_id(match, idx),
        event_date=_extract_date(match),
        r1=float(r1),
        r2=float(r2),
        r3=float(r3),
        r4=float(r4),
        games1=g1,
        games2=g2,
        winner=winner,
        rel1=rel1,
        rel2=rel2,
        rel3=rel3,
        rel4=rel4,
        slot=slot,
        target_pre_rating=float(target_pre),
        target_reliability=target_rel,
        partner_id=partner_id,
        opponent_ids=opponent_ids,
    )


def normalize_matches_for_player(
    matches: Sequence[Dict[str, Any]], player_id: str
) -> List[NormalizedMatch]:
    normalized: List[NormalizedMatch] = []
    for idx, match in enumerate(matches):
        if not isinstance(match, dict):
            continue
        nm = normalize_match_for_player(match, player_id, idx=idx)
        if nm is not None:
            normalized.append(nm)

    normalized.sort(
        key=lambda m: (
            m.event_date is None,
            m.event_date or datetime.max.replace(tzinfo=timezone.utc),
            m.match_id,
        )
    )
    return normalized


def _target_impact(slot: int, impacts: Tuple[float, float, float, float]) -> float:
    return impacts[slot - 1]


def _weighted_multiplier(
    match_rel: Optional[float], current_reliability: Optional[float]
) -> float:
    rel = match_rel if match_rel is not None else current_reliability
    if rel is None:
        rel = 50.0
    weight = rel / 100.0
    if weight < 0.0:
        return 0.0
    if weight > 1.0:
        return 1.0
    return weight


def replay_window(
    predictor: DuprPredictor,
    matches: Sequence[NormalizedMatch],
    mode: str,
    min_rel: Optional[float],
    baseline_rating: Optional[float],
    current_reliability: Optional[float],
) -> Dict[str, Any]:
    if not matches:
        return {
            "matches_considered": 0,
            "matches_used": 0,
            "matches_skipped": 0,
            "baseline_rating": baseline_rating,
            "shadow_rating": baseline_rating,
            "delta": 0.0,
            "higher_of_rating": baseline_rating,
            "partner_diversity": 0,
            "opponent_diversity": 0,
            "skip_reasons": {"insufficient_data": 0, "low_reliability": 0},
        }

    baseline = (
        float(baseline_rating) if baseline_rating is not None else float(matches[0].target_pre_rating)
    )
    shadow = baseline
    used = 0
    skipped = 0
    skip_reasons = {"insufficient_data": 0, "low_reliability": 0}
    partners = set()
    opponents = set()

    for match in matches:
        if mode == "min_rel_threshold":
            if match.target_reliability is None or (
                min_rel is not None and match.target_reliability < min_rel
            ):
                skipped += 1
                skip_reasons["low_reliability"] += 1
                continue

        impacts = predictor.predict_impacts(
            match.r1,
            match.r2,
            match.r3,
            match.r4,
            match.games1,
            match.games2,
            match.winner,
            rel1=match.rel1,
            rel2=match.rel2,
            rel3=match.rel3,
            rel4=match.rel4,
        )
        impact = _target_impact(match.slot, impacts)
        if mode == "weighted_current":
            impact *= _weighted_multiplier(match.target_reliability, current_reliability)

        shadow += impact
        used += 1
        if match.partner_id:
            partners.add(match.partner_id)
        for opp in match.opponent_ids:
            if opp:
                opponents.add(opp)

    return {
        "matches_considered": len(matches),
        "matches_used": used,
        "matches_skipped": skipped,
        "baseline_rating": baseline,
        "shadow_rating": shadow,
        "delta": shadow - baseline,
        "higher_of_rating": max(baseline, shadow),
        "partner_diversity": len(partners),
        "opponent_diversity": len(opponents),
        "skip_reasons": skip_reasons,
    }


def simulate_shadow_reset(
    predictor: DuprPredictor,
    raw_matches: Sequence[Dict[str, Any]],
    player_id: str,
    windows: Sequence[int] = (8, 16, 24),
    mode: str = "include_all",
    min_rel: Optional[float] = None,
    baseline_rating: Optional[float] = None,
    current_reliability: Optional[float] = None,
) -> Dict[str, Any]:
    mode = mode.strip().lower()
    if mode not in {"include_all", "min_rel_threshold", "weighted_current"}:
        raise ValueError(f"Unsupported mode: {mode}")

    normalized = normalize_matches_for_player(raw_matches, player_id=str(player_id))
    if not normalized:
        raise ValueError("No usable matches found for this player.")

    unique_windows = sorted({int(w) for w in windows if int(w) > 0})
    results: Dict[str, Any] = {}
    for window in unique_windows:
        subset = normalized[-window:]
        result = replay_window(
            predictor=predictor,
            matches=subset,
            mode=mode,
            min_rel=min_rel,
            baseline_rating=baseline_rating,
            current_reliability=current_reliability,
        )
        result["window"] = window
        result["total_player_matches_available"] = len(normalized)
        result["meets_minimum_8_matches"] = result["matches_used"] >= 8
        result["meets_partner_diversity_2"] = result["partner_diversity"] >= 2
        result["qualifies_reset_style"] = (
            result["meets_minimum_8_matches"] and result["meets_partner_diversity_2"]
        )
        results[str(window)] = result

    return {
        "player_id": str(player_id),
        "mode": mode,
        "windows": unique_windows,
        "total_player_matches_available": len(normalized),
        "results": results,
    }

