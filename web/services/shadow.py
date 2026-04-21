"""
Shadow-reset simulator for a single DUPR player.

Answers: "If DUPR reset my reliability to 0% today and replayed every match
since <cutoff_date> against my pre-reset baseline, where would I land?"

This wraps the existing `dupr_shadow_calculator` module with three changes:

1. **Date-windowed replay** — instead of last-N matches, we keep every match
   whose `event_date >= cutoff_date`. Default cutoff is 2026-04-16 (DUPR's
   most recent publicly-discussed ratings overhaul), overridable.
2. **Growing target reliability for the shadow branch** — we rerun the
   predictor with the target slot's reliability starting at 0% and growing
   +5% per match (capped at the player's current DUPR `doublesReliabilityScore`).
   Opponents keep their real reliability values so the rest of the table
   behaves normally.
3. **Actual branch uses DUPR's authoritative deltas** — the "Replay ·
   current rels" trajectory sums DUPR's own
   `matchDoubleRatingImpactPlayer{1,2}` values from each match payload, not
   our reverse-engineered predictor. This guarantees the replay end-state
   mirrors the player's live DUPR rating (to within DUPR's rounding). The
   predictor is kept as a fallback when those fields are missing.

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
from typing import Any, Dict, List, Optional, Sequence, Tuple

from dupr_predictor import DuprPredictor
from dupr_shadow_calculator import (
    NormalizedMatch,
    normalize_matches_for_player,
)

from web.services.dupr_live import _get_live_client, _has_live_credentials


_LOG = logging.getLogger("duprly.shadow")

# DUPR's most recent public ratings overhaul. The UI defaults to this cutoff so
# the "what-if reset" story matches DUPR's own framing — overridable from the
# form.
DEFAULT_CUTOFF = date(2026, 4, 16)

# Simple linear reliability-growth model used for the shadow simulation.
# The premise: if DUPR reset your reliability to 0% today, every subsequent
# rated match would nudge it back up. DUPR's internal growth curve isn't
# public, but empirically players cross ~100% after ~20 rated matches, so
# we approximate +5% per match, capped by the player's observed `current`
# reliability ceiling (or 100% if the API didn't return one).
SHADOW_REL_INC_PER_MATCH = 5.0
SHADOW_REL_MAX_DEFAULT = 100.0


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
    actual_impacts: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    # What the shadow sim would have done (target rel forced to 0, then
    # growing per `SHADOW_REL_INC_PER_MATCH` as matches are replayed).
    shadow_impact: float = 0.0
    shadow_running: float = 0.0
    shadow_impacts: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    # Target-slot reliability the shadow sim used for THIS match (pre-match).
    # Starts near 0 and grows over time — gives the UI a per-row trajectory.
    shadow_reliability: float = 0.0
    # Per-slot player meta (name / dupr_id / image_url / …) so the per-row
    # DUPR-style match card can render avatars + profile links.
    players: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ShadowSummary:
    player_id: str
    player_name: Optional[str]
    cutoff_date: str
    baseline_rating: float
    # Reliability observed on the earliest eligible match (i.e. at the
    # cutoff). Surfaces as "rel at baseline" in the UI so users can see
    # where their real rel started when the simulated reset happened.
    baseline_reliability: Optional[float]
    current_rating: Optional[float]
    current_reliability: Optional[float]
    matches_since_cutoff: int
    matches_used: int
    actual_delta: float
    actual_final_rating: float
    actual_final_reliability: Optional[float]
    shadow_delta: float
    shadow_final_rating: float
    shadow_final_reliability: float
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


def _extract_match_players(raw_match: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pull per-slot player meta (id / name / avatar / age / loc) out of a
    raw DUPR match payload. Returns a 4-element list indexed by slot (0..3
    maps to slots 1..4). Missing slots become empty dicts so downstream
    template code can safely render placeholders.
    """
    out: List[Dict[str, Any]] = [{}, {}, {}, {}]
    teams = raw_match.get("teams")
    if not isinstance(teams, list) or len(teams) < 2:
        return out

    def _slot_meta(p: Any) -> Dict[str, Any]:
        if not isinstance(p, dict):
            return {}
        pid_raw = p.get("id") or p.get("playerId") or p.get("userId") or p.get("duprId")
        pid = str(pid_raw) if pid_raw is not None else None
        full = p.get("fullName") or " ".join(
            x for x in [p.get("firstName"), p.get("lastName")] if x
        ).strip()
        return {
            "dupr_id": pid,
            "name": full or None,
            "image_url": p.get("imageUrl"),
            "age": p.get("age"),
            "gender": p.get("gender"),
            "short_address": p.get("shortAddress") or p.get("addressShort"),
        }

    team0 = teams[0] if isinstance(teams[0], dict) else {}
    team1 = teams[1] if isinstance(teams[1], dict) else {}

    def _team_players(team: Dict[str, Any]) -> Tuple[Any, Any]:
        p1 = team.get("player1") if isinstance(team.get("player1"), dict) else None
        p2 = team.get("player2") if isinstance(team.get("player2"), dict) else None
        if p1 and p2:
            return p1, p2
        players = team.get("players")
        if isinstance(players, list) and len(players) >= 2:
            return players[0], players[1]
        return p1, p2

    t0p1, t0p2 = _team_players(team0)
    t1p1, t1p2 = _team_players(team1)
    out[0] = _slot_meta(t0p1)
    out[1] = _slot_meta(t0p2)
    out[2] = _slot_meta(t1p1)
    out[3] = _slot_meta(t1p2)
    return out


def _index_matches_by_id(raw_matches: Sequence[Any]) -> Dict[str, Dict[str, Any]]:
    """Build a match_id -> raw_match lookup so we can pair NormalizedMatch
    rows back with their source payload for player metadata."""
    out: Dict[str, Dict[str, Any]] = {}
    for idx, m in enumerate(raw_matches):
        if not isinstance(m, dict):
            continue
        raw_id = m.get("matchId") or m.get("match_id") or m.get("id")
        key = str(raw_id) if raw_id is not None else f"match-{idx}"
        out[key] = m
    return out


def _extract_dupr_impacts(
    raw_match: Dict[str, Any],
) -> Optional[Tuple[float, float, float, float]]:
    """Pull DUPR's *own* per-slot doubles rating impacts out of a raw match.

    These live on each team's `preMatchRatingAndImpact` block as
    `matchDoubleRatingImpactPlayer{1,2}` and represent what DUPR actually
    applied to each player after the match — i.e. the authoritative delta.

    Slot convention matches `dupr_shadow_calculator.normalize_matches_for_player`:
        slot 1 = teams[0].player1     slot 2 = teams[0].player2
        slot 3 = teams[1].player1     slot 4 = teams[1].player2

    Returns a 4-tuple (floats) when all four impacts are present, else None
    so the caller can fall back to the predictor.
    """
    teams = raw_match.get("teams")
    if not isinstance(teams, list) or len(teams) < 2:
        return None
    out: List[float] = []
    for t_idx in (0, 1):
        team = teams[t_idx] if isinstance(teams[t_idx], dict) else {}
        block = team.get("preMatchRatingAndImpact")
        if not isinstance(block, dict):
            return None
        for p_idx in (1, 2):
            v = block.get(f"matchDoubleRatingImpactPlayer{p_idx}")
            if v is None:
                return None
            try:
                out.append(float(v))
            except (TypeError, ValueError):
                return None
    return (out[0], out[1], out[2], out[3])


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
    raw_by_id = _index_matches_by_id(raw_matches)

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

    baseline_reliability: Optional[float] = None
    if eligible and eligible[0].target_reliability is not None:
        baseline_reliability = float(eligible[0].target_reliability)

    # Shadow rel ceiling — cap growth at what the player is actually known to
    # reach today (falls back to 100% if the API didn't return one).
    rel_ceiling = float(meta.get("current_reliability") or SHADOW_REL_MAX_DEFAULT)
    rel_ceiling = max(0.0, min(SHADOW_REL_MAX_DEFAULT, rel_ceiling))

    predictor_path = model_file or _default_model_path()
    predictor = DuprPredictor(predictor_path)

    actual_running = float(baseline_rating)
    shadow_running = float(baseline_rating)
    rows: List[ShadowMatchRow] = []
    partners = set()
    opponents = set()
    # Track the latest per-match reliability we actually saw. DUPR's match
    # history endpoint currently does NOT return per-match reliability, so
    # this typically stays None across the window and we fall back to the
    # player's live `doublesReliabilityScore`.
    actual_final_rel: Optional[float] = None

    for idx, m in enumerate(eligible):
        # Pre-match shadow reliability: grows from 0% at a steady pace until
        # it reaches the player's real current ceiling.
        shadow_rel_pre = min(rel_ceiling, idx * SHADOW_REL_INC_PER_MATCH)

        raw_match = raw_by_id.get(m.match_id) or {}
        # "Actual" = what DUPR really did. DUPR embeds the authoritative
        # per-player impact in `teams[*].preMatchRatingAndImpact.matchDoubleRatingImpactPlayerN`,
        # so we use those directly. Summing them reproduces the player's live
        # DUPR rating exactly. If the payload is missing fields we fall back
        # to our reverse-engineered predictor — but that path is lossy
        # because the match-history API doesn't return per-match reliability.
        dupr_imp = _extract_dupr_impacts(raw_match)
        if dupr_imp is not None:
            actual_imp_tuple = dupr_imp
        else:
            actual_imp_tuple = predictor.predict_impacts(
                m.r1, m.r2, m.r3, m.r4,
                m.games1, m.games2, m.winner,
                rel1=m.rel1, rel2=m.rel2, rel3=m.rel3, rel4=m.rel4,
            )
        actual_impact = _target_slot_impact(m.slot, actual_imp_tuple)

        # Shadow: same match, but overwrite target player's reliability with
        # the growing curve (opponents / partner keep their real rels so
        # multipliers stay honest for the rest of the table).
        shadow_rels = _override_reliability_for_slot(m, m.slot, shadow_rel_pre)
        shadow_imp_tuple = predictor.predict_impacts(
            m.r1, m.r2, m.r3, m.r4,
            m.games1, m.games2, m.winner,
            rel1=shadow_rels[0], rel2=shadow_rels[1],
            rel3=shadow_rels[2], rel4=shadow_rels[3],
        )
        shadow_impact = _target_slot_impact(m.slot, shadow_imp_tuple)

        actual_running += actual_impact
        shadow_running += shadow_impact

        if m.target_reliability is not None:
            actual_final_rel = float(m.target_reliability)

        players_meta = _extract_match_players(raw_match)

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
                actual_impacts=tuple(round(x, 6) for x in actual_imp_tuple),
                shadow_impact=round(shadow_impact, 6),
                shadow_running=round(shadow_running, 4),
                shadow_impacts=tuple(round(x, 6) for x in shadow_imp_tuple),
                shadow_reliability=round(shadow_rel_pre, 2),
                players=players_meta,
            )
        )
        if m.partner_id:
            partners.add(m.partner_id)
        for o in m.opponent_ids:
            if o:
                opponents.add(o)

    actual_delta = actual_running - baseline_rating
    shadow_delta = shadow_running - baseline_rating
    shadow_final_rel = (
        min(rel_ceiling, max(0, len(rows) - 1) * SHADOW_REL_INC_PER_MATCH)
        if rows
        else 0.0
    )
    # Fall back to the player's live rel when the match-history endpoint
    # didn't surface per-match values — that way the summary card shows
    # "rel 100%" instead of "rel —" for fully-verified players.
    if actual_final_rel is None and meta.get("current_reliability") is not None:
        actual_final_rel = float(meta["current_reliability"])
    if baseline_reliability is None and meta.get("current_reliability") is not None:
        # We don't know historical rel, but surfacing current rel as the
        # baseline beats showing nothing — users read this as "here's where
        # your rel is today, starting point for the shadow trajectory".
        baseline_reliability = float(meta["current_reliability"])

    return ShadowSummary(
        player_id=resolved_id,
        player_name=meta.get("player_name"),
        cutoff_date=cutoff.isoformat(),
        baseline_rating=round(float(baseline_rating), 4),
        baseline_reliability=(
            round(baseline_reliability, 2) if baseline_reliability is not None else None
        ),
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
        actual_final_reliability=(
            round(actual_final_rel, 2) if actual_final_rel is not None else None
        ),
        shadow_delta=round(shadow_delta, 4),
        shadow_final_rating=round(shadow_running, 4),
        shadow_final_reliability=round(shadow_final_rel, 2),
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
