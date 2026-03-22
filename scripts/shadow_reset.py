#!/usr/bin/env python3
"""
Compute reset-style shadow ratings over last-N DUPR matches.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dupr_client import DuprClient
from dupr_predictor import DuprPredictor
from shadow_reset_history import persist_shadow_run
from dupr_shadow_calculator import simulate_shadow_reset


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_doubles_rating(player_data: Dict[str, Any]) -> Optional[float]:
    if not isinstance(player_data, dict):
        return None
    ratings = player_data.get("ratings")
    if isinstance(ratings, dict):
        for key in ("doubles", "doublesRating", "doubles_rating"):
            val = _safe_float(ratings.get(key))
            if val is not None:
                return val
    for key in ("doubles", "doublesRating", "doubles_rating"):
        val = _safe_float(player_data.get(key))
        if val is not None:
            return val
    return None


def _extract_reliability(player_data: Dict[str, Any]) -> Optional[float]:
    if not isinstance(player_data, dict):
        return None
    ratings = player_data.get("ratings")
    keys = (
        "doublesReliabilityScore",
        "doublesVerified",
        "reliability",
        "doublesReliability",
        "reliabilityScore",
        "verified",
    )
    if isinstance(ratings, dict):
        for key in keys:
            val = _safe_float(ratings.get(key))
            if val is not None:
                return val
    for key in keys:
        val = _safe_float(player_data.get(key))
        if val is not None:
            return val
    return None


def _print_result_table(payload: Dict[str, Any]) -> None:
    mode = payload.get("mode")
    windows = payload.get("windows", [])
    results = payload.get("results", {})
    print("")
    print(f"Mode: {mode}")
    print(
        "window | baseline | shadow | delta | higher_of | used/considered | skipped | "
        "partners | opponents | qualifies"
    )
    print("-" * 110)
    for window in windows:
        row = results.get(str(window), {})
        baseline = row.get("baseline_rating")
        shadow = row.get("shadow_rating")
        delta = row.get("delta")
        higher_of = row.get("higher_of_rating")
        used = row.get("matches_used", 0)
        considered = row.get("matches_considered", 0)
        skipped = row.get("matches_skipped", 0)
        partner_div = row.get("partner_diversity", 0)
        opp_div = row.get("opponent_diversity", 0)
        qualifies = "yes" if row.get("qualifies_reset_style") else "no"
        print(
            f"{window:>6} | {baseline:>8.3f} | {shadow:>6.3f} | {delta:>+6.3f} | "
            f"{higher_of:>9.3f} | {used:>3}/{considered:<3} | {skipped:>7} | "
            f"{partner_div:>8} | {opp_div:>9} | {qualifies}"
        )

    print("")
    print("Skip reason counts per window (if any):")
    for window in windows:
        row = results.get(str(window), {})
        reasons = row.get("skip_reasons", {})
        if row.get("matches_skipped", 0) == 0:
            continue
        print(f"  window {window}: {reasons}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute reset-style shadow rating over last N DUPR matches."
    )
    parser.add_argument("--dupr-id", required=True, help="Player id or short DUPR id")
    parser.add_argument(
        "--windows",
        nargs="+",
        type=int,
        default=[8, 16, 24],
        help="Rolling windows to compute (default: 8 16 24)",
    )
    parser.add_argument(
        "--mode",
        choices=["include_all", "min_rel_threshold", "weighted_current"],
        default="include_all",
        help="Reliability handling mode",
    )
    parser.add_argument(
        "--min-rel",
        type=float,
        default=90.0,
        help="Minimum reliability threshold for min_rel_threshold mode",
    )
    parser.add_argument(
        "--baseline-rating",
        type=float,
        default=None,
        help="Optional manual baseline rating. Defaults to player current doubles rating.",
    )
    parser.add_argument(
        "--current-reliability",
        type=float,
        default=None,
        help="Optional reliability proxy for weighted_current mode.",
    )
    parser.add_argument(
        "--model-file",
        default="dupr_model.json",
        help="Path to fitted predictor model JSON.",
    )
    parser.add_argument(
        "--history-db",
        default="shadow_reset_history.db",
        help="SQLite file path for persisting run history.",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Disable writing run results to SQLite history.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv()

    dupr = DuprClient(verbose=False)
    username = os.getenv("DUPR_USERNAME")
    password = os.getenv("DUPR_PASSWORD")
    if not username or not password:
        print("Missing DUPR_USERNAME or DUPR_PASSWORD in environment.")
        return 1

    rc = dupr.auth_user(username, password)
    if rc not in (0, 200):
        print(f"Authentication failed with status: {rc}")
        return 1

    rc_player, player = dupr.get_player(args.dupr_id)
    if rc_player != 200 or not player:
        print(f"Failed to resolve player: {args.dupr_id} (status: {rc_player})")
        return 1

    resolved_player_id = str(player.get("id") or args.dupr_id)
    baseline = args.baseline_rating
    if baseline is None:
        baseline = _extract_doubles_rating(player)
    current_rel = args.current_reliability
    if current_rel is None:
        current_rel = _extract_reliability(player)

    if baseline is None:
        print("Could not determine baseline rating; pass --baseline-rating explicitly.")
        return 1

    rc_matches, matches = dupr.get_member_match_history_p(resolved_player_id)
    if rc_matches != 200 or not isinstance(matches, list):
        print(f"Failed to fetch match history (status: {rc_matches}).")
        return 1

    predictor = DuprPredictor(args.model_file)
    payload = simulate_shadow_reset(
        predictor=predictor,
        raw_matches=matches,
        player_id=resolved_player_id,
        windows=args.windows,
        mode=args.mode,
        min_rel=args.min_rel,
        baseline_rating=baseline,
        current_reliability=current_rel,
    )

    print(f"Player: {player.get('fullName', 'Unknown')} ({args.dupr_id})")
    print(f"Resolved player id: {resolved_player_id}")
    print(f"Baseline rating: {baseline:.3f}")
    if current_rel is not None:
        print(f"Current reliability proxy: {current_rel:.1f}")
    else:
        print("Current reliability proxy: unavailable")
    print(f"Total usable matches found: {payload.get('total_player_matches_available', 0)}")
    _print_result_table(payload)
    if not args.no_log:
        run_id = persist_shadow_run(
            payload=payload,
            player_name=player.get("fullName"),
            requested_dupr_id=args.dupr_id,
            baseline_rating=baseline,
            current_reliability=current_rel,
            db_path=args.history_db,
        )
        print(f"Saved run to SQLite: {args.history_db} (run_id={run_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

