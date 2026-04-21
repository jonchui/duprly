"""
Shadow-reset simulator for a single DUPR player.

Answers: "If DUPR reset my reliability to 0% today and replayed every match
since <cutoff_date> against my pre-reset baseline, where would I land?"

This wraps the existing `dupr_shadow_calculator` module with two changes:

1. **Date-windowed replay** — instead of last-N matches, we keep every match
   whose `event_date >= cutoff_date`. Default cutoff is 2024-04-16 (the start
   of DUPR's last publicly-discussed ratings overhaul), overridable.
2. **Forced 0% reliability for the target player** — we rerun the predictor
   with the target slot's reliability set to 0, which in the fitted model
   yields the maximum per-match impact (multiplier = 1.0). Opponents keep
   their real reliability values so the rest of the table behaves normally.

Live DUPR credentials (DUPR_USERNAME / DUPR_PASSWORD) are required — this
feature inherently needs each player's match history, which is not cached
locally. If creds are missing, `simulate` raises `ShadowUnavailable`.

Result shape is designed for JSON and HTML rendering side-by-side.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from dupr_predictor import DuprPredictor
from dupr_shadow_calculator import (
    NormalizedMatch,
    normalize_matches_for_player,
)

from web.services.dupr_live import _get_live_client, _has_live_credentials


_LOG = logging.getLogger("duprly.shadow")

# DUPR's most recent "reset" event started around this date — overridable from
# the UI. This is our out-of-the-box default for the "since the reset" cutoff.
DEFAULT_CUTOFF = date(2024, 4, 16)


class ShadowUnavailable(RuntimeError):
    """Raised when live DUPR credentials are missing or lookup fails."""


@dataclass
class ShadowMatchRow:
    match_id: str
    event_date: Optional[str]  # ISO string for JSON friendliness
    r1: float
    r2: float
    r3: float
    r4: float
    games1: int
    games2: int
    winner: int
    slot: int
    target_pre_rating: float
    target_reliability: Optional[float]
    # What DUPR actually did (real reliability values on the match).
    actual_impact: float
    actual_running: float
    # What the shadow sim would have done (target rel forced to 0).
    shadow_impact: float
    shadow_running: float


@dataclass
class ShadowSummary:
    player_id: str
    player_name: Optional[str]
    cutoff_date: str
    baseline_rating: float
    current_rating: Optional[float]
    current_reliability: Optional[float]
    matches_since_cutoff: int
    matches_used: int
    actual_delta: float
    actual_final_rating: float
    shadow_delta: float
    shadow_final_rating: float
    higher_of_rating: float
    partner_diversity: int
    opponent_diversity: int
    rows: List[ShadowMatchRow] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


def _filter_by_cutoff(
    matches: Sequence[NormalizedMatch], cutoff: date
) -> List[NormalizedMatch]:
    """Keep only matches on or after cutoff. Matches w/o a date are kept as
    'unknown-date' and ordered last (already handled by normalize_...)."""
    kept: List[NormalizedMatch] = []
    cutoff_dt = datetime(cutoff.year, cutoff.month, cutoff.day, tzinfo=timezone.utc)
    for m in matches:
        if m.event_date is None or m.event_date >= cutoff_dt:
            kept.append(m)
    return kept


def _target_slot_impact(slot: int, impacts) -> float:
    return impacts[slot - 1]


def _override_reliability_for_slot(
    match: NormalizedMatch, slot: int, new_value: float
) -> tuple:
    """Return (rel1, rel2, rel3, rel4) with `slot`'s entry replaced."""
    rels = [match.rel1, match.rel2, match.rel3, match.rel4]
    rels[slot - 1] = new_value
    return tuple(rels)


def _extract_player_meta(player: Dict[str, Any]) -> Dict[str, Any]:
    """Pull current rating + reliability + name from a /player API response."""
    ratings = player.get("ratings") if isinstance(player.get("ratings"), dict) else {}

    def _f(d: Dict[str, Any], *keys) -> Optional[float]:
        for k in keys:
            v = d.get(k)
            if v is None:
                continue
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
        return None

    current = _f(ratings, "doubles", "doublesRating") or _f(
        player, "doubles", "doublesRating"
    )
    rel = _f(
        ratings,
        "doublesReliabilityScore",
        "doublesReliability",
        "reliability",
    ) or _f(
        player,
        "doublesReliabilityScore",
        "doublesReliability",
        "reliability",
    )
    name = player.get("fullName") or " ".join(
        x for x in [player.get("firstName"), player.get("lastName")] if x
    ).strip() or None
    return {"current_rating": current, "current_reliability": rel, "player_name": name}


def simulate(
    dupr_id: str,
    baseline_rating: Optional[float] = None,
    cutoff: Optional[date] = None,
    model_file: Optional[str] = None,
) -> ShadowSummary:
    """Run the shadow-reset simulation for one player."""
    if not _has_live_credentials():
        raise ShadowUnavailable(
            "DUPR live credentials not configured — set DUPR_USERNAME and DUPR_PASSWORD."
        )
    cutoff = cutoff or DEFAULT_CUTOFF

    try:
        client = _get_live_client()
    except Exception as exc:
        raise ShadowUnavailable(f"DUPR auth failed: {exc}") from exc

    rc, player = client.get_player(str(dupr_id))
    if rc != 200 or not player:
        raise ShadowUnavailable(f"DUPR player lookup failed (status {rc}) for {dupr_id!r}")

    resolved_id = str(player.get("id") or dupr_id)
    meta = _extract_player_meta(player)

    rc_m, raw_matches = client.get_member_match_history_p(resolved_id)
    if rc_m != 200 or not isinstance(raw_matches, list):
        raise ShadowUnavailable(f"DUPR match-history fetch failed (status {rc_m})")

    all_normalized = normalize_matches_for_player(raw_matches, player_id=resolved_id)
    eligible = _filter_by_cutoff(all_normalized, cutoff)

    # Baseline: explicit > API-inferred pre-rating of earliest eligible match >
    # current doubles rating.
    if baseline_rating is None:
        if eligible:
            baseline_rating = float(eligible[0].target_pre_rating)
        elif meta.get("current_rating") is not None:
            baseline_rating = float(meta["current_rating"])
        else:
            raise ShadowUnavailable(
                "No baseline rating available — pass baseline_rating explicitly."
            )

    predictor_path = model_file or _default_model_path()
    predictor = DuprPredictor(predictor_path)

    actual_running = float(baseline_rating)
    shadow_running = float(baseline_rating)
    rows: List[ShadowMatchRow] = []
    partners = set()
    opponents = set()

    for m in eligible:
        # Actual: use the real per-player reliability values.
        actual_imp_tuple = predictor.predict_impacts(
            m.r1, m.r2, m.r3, m.r4,
            m.games1, m.games2, m.winner,
            rel1=m.rel1, rel2=m.rel2, rel3=m.rel3, rel4=m.rel4,
        )
        actual_impact = _target_slot_impact(m.slot, actual_imp_tuple)

        # Shadow: same match, but force target player's reliability to 0.
        shadow_rels = _override_reliability_for_slot(m, m.slot, 0.0)
        shadow_imp_tuple = predictor.predict_impacts(
            m.r1, m.r2, m.r3, m.r4,
            m.games1, m.games2, m.winner,
            rel1=shadow_rels[0], rel2=shadow_rels[1],
            rel3=shadow_rels[2], rel4=shadow_rels[3],
        )
        shadow_impact = _target_slot_impact(m.slot, shadow_imp_tuple)

        actual_running += actual_impact
        shadow_running += shadow_impact

        rows.append(
            ShadowMatchRow(
                match_id=m.match_id,
                event_date=m.event_date.isoformat() if m.event_date else None,
                r1=m.r1, r2=m.r2, r3=m.r3, r4=m.r4,
                games1=m.games1, games2=m.games2, winner=m.winner,
                slot=m.slot,
                target_pre_rating=m.target_pre_rating,
                target_reliability=m.target_reliability,
                actual_impact=round(actual_impact, 6),
                actual_running=round(actual_running, 4),
                shadow_impact=round(shadow_impact, 6),
                shadow_running=round(shadow_running, 4),
            )
        )
        if m.partner_id:
            partners.add(m.partner_id)
        for o in m.opponent_ids:
            if o:
                opponents.add(o)

    actual_delta = actual_running - baseline_rating
    shadow_delta = shadow_running - baseline_rating

    return ShadowSummary(
        player_id=resolved_id,
        player_name=meta.get("player_name"),
        cutoff_date=cutoff.isoformat(),
        baseline_rating=round(float(baseline_rating), 4),
        current_rating=(
            round(float(meta["current_rating"]), 4)
            if meta.get("current_rating") is not None
            else None
        ),
        current_reliability=(
            round(float(meta["current_reliability"]), 2)
            if meta.get("current_reliability") is not None
            else None
        ),
        matches_since_cutoff=len(eligible),
        matches_used=len(rows),
        actual_delta=round(actual_delta, 4),
        actual_final_rating=round(actual_running, 4),
        shadow_delta=round(shadow_delta, 4),
        shadow_final_rating=round(shadow_running, 4),
        higher_of_rating=round(max(baseline_rating, shadow_running), 4),
        partner_diversity=len(partners),
        opponent_diversity=len(opponents),
        rows=rows,
    )


def _default_model_path() -> str:
    """Locate `dupr_model.json` at the repo root (one level above web/)."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.normpath(os.path.join(here, "..", "..", "dupr_model.json"))
    if os.path.isfile(candidate):
        return candidate
    # Fallback: cwd (matches CLI default).
    return "dupr_model.json"
