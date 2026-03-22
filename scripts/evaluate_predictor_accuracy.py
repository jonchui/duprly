#!/usr/bin/env python3
"""
Evaluate DuprPredictor accuracy on Jon's last N matches from dupr.sqlite.

Outputs two scorecards:
1) Jon-only player impacts
2) All-player impacts (all 4 players per match)

NOTE:
This evaluator is the source of truth for model trustworthiness. If strict
thresholds fail, downstream simulation scripts should be treated as directional
only (not production-equivalent DUPR outcomes).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.stats import spearmanr
from sqlalchemy import select

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dupr_db import ClubMatchRaw, open_db
from dupr_predictor import DuprPredictor


JON_ID_NUMERIC = "4405492894"
JON_ID_SHORT = "0YVNWN"
STRICT_THRESHOLDS = {
    "r2_min": 0.70,
    "pearson_min": 0.85,
    "mae_max": 0.020,
}


@dataclass
class EvalMatch:
    match_id: str
    event_date: Optional[datetime]
    r1: float
    r2: float
    r3: float
    r4: float
    rel1: Optional[float]
    rel2: Optional[float]
    rel3: Optional[float]
    rel4: Optional[float]
    imp1: float
    imp2: float
    imp3: float
    imp4: float
    games1: int
    games2: int
    winner: int
    jon_slot: int


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


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d"):
        try:
            dt = datetime.fromisoformat(text) if fmt is None else datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _extract_team_players(team: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    p1 = team.get("player1") if isinstance(team.get("player1"), dict) else None
    p2 = team.get("player2") if isinstance(team.get("player2"), dict) else None
    if p1 and p2:
        return p1, p2
    players = team.get("players")
    if isinstance(players, list) and len(players) >= 2:
        return (
            players[0] if isinstance(players[0], dict) else {},
            players[1] if isinstance(players[1], dict) else {},
        )
    return p1 or {}, p2 or {}


def _extract_player_ids(player: Dict[str, Any]) -> List[str]:
    values = []
    if not isinstance(player, dict):
        return values
    for key in ("id", "duprId", "playerId", "userId"):
        raw = player.get(key)
        if raw is not None:
            values.append(str(raw))
    return values


def _extract_player_rel(player: Dict[str, Any]) -> Optional[float]:
    if not isinstance(player, dict):
        return None
    for key in (
        "doublesReliabilityScore",
        "doublesVerified",
        "reliability",
        "doublesReliability",
        "reliabilityScore",
        "verified",
    ):
        val = _safe_float(player.get(key))
        if val is not None:
            return val
    ratings = player.get("ratings")
    if isinstance(ratings, dict):
        for key in (
            "doublesReliabilityScore",
            "doublesVerified",
            "reliability",
            "doublesReliability",
            "reliabilityScore",
            "verified",
        ):
            val = _safe_float(ratings.get(key))
            if val is not None:
                return val
    return None


def _games_from_team(team: Dict[str, Any]) -> int:
    vals = [_safe_int(team.get(k)) for k in ("game1", "game2", "game3")]
    vals = [v for v in vals if v is not None and v >= 0]
    if vals:
        return int(sum(vals))
    fallback = _safe_int(team.get("score"))
    return fallback if fallback is not None else 0


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if ss_tot == 0.0:
        return float("nan")
    return 1.0 - (ss_res / ss_tot)


def _pearson(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if y_true.size < 2:
        return float("nan")
    if np.std(y_true) == 0 or np.std(y_pred) == 0:
        return float("nan")
    return float(np.corrcoef(y_true, y_pred)[0, 1])


def _spearman(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if y_true.size < 2:
        return float("nan")
    corr, _ = spearmanr(y_true, y_pred)
    return float(corr) if corr is not None else float("nan")


def _sign_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if y_true.size == 0:
        return float("nan")
    signs_true = np.sign(y_true)
    signs_pred = np.sign(y_pred)
    return float(np.mean(signs_true == signs_pred))


def _score_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
    errors = y_pred - y_true
    abs_errors = np.abs(errors)
    return {
        "n_points": int(y_true.size),
        "mae": float(np.mean(abs_errors)),
        "rmse": float(np.sqrt(np.mean(errors**2))),
        "pearson": _pearson(y_true, y_pred),
        "spearman": _spearman(y_true, y_pred),
        "r2": _r2_score(y_true, y_pred),
        "sign_accuracy": _sign_accuracy(y_true, y_pred),
        "p50_abs_error": float(np.percentile(abs_errors, 50)),
        "p90_abs_error": float(np.percentile(abs_errors, 90)),
        "p95_abs_error": float(np.percentile(abs_errors, 95)),
    }


def _grade_strict(metrics: Dict[str, Any]) -> Dict[str, Any]:
    mae_ok = metrics["mae"] <= STRICT_THRESHOLDS["mae_max"]
    pearson_ok = metrics["pearson"] >= STRICT_THRESHOLDS["pearson_min"]
    r2_ok = metrics["r2"] >= STRICT_THRESHOLDS["r2_min"]
    passed = bool(mae_ok and pearson_ok and r2_ok)
    return {
        "pass": passed,
        "checks": {
            "mae_ok": mae_ok,
            "pearson_ok": pearson_ok,
            "r2_ok": r2_ok,
        },
        "gaps_to_target": {
            "mae_over": float(max(0.0, metrics["mae"] - STRICT_THRESHOLDS["mae_max"])),
            "pearson_under": float(
                max(0.0, STRICT_THRESHOLDS["pearson_min"] - metrics["pearson"])
            ),
            "r2_under": float(max(0.0, STRICT_THRESHOLDS["r2_min"] - metrics["r2"])),
        },
    }


def _load_jon_matches(limit: int) -> Tuple[List[EvalMatch], Dict[str, int]]:
    eng = open_db()
    rows = []
    skipped_missing_fields = 0
    skipped_no_jon = 0
    reliability_points = 0
    reliability_total = 0

    jon_ids = {JON_ID_NUMERIC, JON_ID_SHORT}

    with eng.connect() as conn:
        result = conn.execute(select(ClubMatchRaw))
        for row in result:
            try:
                data = json.loads(row.raw_json)
            except Exception:
                continue
            teams = data.get("teams")
            if not isinstance(teams, list) or len(teams) != 2:
                continue
            t0 = teams[0] if isinstance(teams[0], dict) else {}
            t1 = teams[1] if isinstance(teams[1], dict) else {}
            t0p1, t0p2 = _extract_team_players(t0)
            t1p1, t1p2 = _extract_team_players(t1)
            slot_to_player = {1: t0p1, 2: t0p2, 3: t1p1, 4: t1p2}

            jon_slot = None
            for slot, player in slot_to_player.items():
                if set(_extract_player_ids(player)).intersection(jon_ids):
                    jon_slot = slot
                    break
            if jon_slot is None:
                skipped_no_jon += 1
                continue

            pre0 = t0.get("preMatchRatingAndImpact") if isinstance(t0.get("preMatchRatingAndImpact"), dict) else {}
            pre1 = t1.get("preMatchRatingAndImpact") if isinstance(t1.get("preMatchRatingAndImpact"), dict) else {}
            r1 = _safe_float(pre0.get("preMatchDoubleRatingPlayer1"))
            r2 = _safe_float(pre0.get("preMatchDoubleRatingPlayer2"))
            r3 = _safe_float(pre1.get("preMatchDoubleRatingPlayer1"))
            r4 = _safe_float(pre1.get("preMatchDoubleRatingPlayer2"))
            i1 = _safe_float(pre0.get("matchDoubleRatingImpactPlayer1"))
            i2 = _safe_float(pre0.get("matchDoubleRatingImpactPlayer2"))
            i3 = _safe_float(pre1.get("matchDoubleRatingImpactPlayer1"))
            i4 = _safe_float(pre1.get("matchDoubleRatingImpactPlayer2"))
            if None in (r1, r2, r3, r4, i1, i2, i3, i4):
                skipped_missing_fields += 1
                continue

            rel_map = {}
            crawl_meta = data.get("_crawl_metadata")
            if isinstance(crawl_meta, dict):
                rel_data = crawl_meta.get("reliability")
                if isinstance(rel_data, dict):
                    rel_map = {
                        1: _safe_float(rel_data.get("player1")),
                        2: _safe_float(rel_data.get("player2")),
                        3: _safe_float(rel_data.get("player3")),
                        4: _safe_float(rel_data.get("player4")),
                    }
            if not rel_map:
                rel_map = {
                    1: _extract_player_rel(t0p1),
                    2: _extract_player_rel(t0p2),
                    3: _extract_player_rel(t1p1),
                    4: _extract_player_rel(t1p2),
                }
            for slot in (1, 2, 3, 4):
                reliability_total += 1
                if rel_map.get(slot) is not None:
                    reliability_points += 1

            winner = 1 if bool(t0.get("winner")) else 2
            rows.append(
                EvalMatch(
                    match_id=str(row.match_id),
                    event_date=_parse_dt(data.get("eventDate") or row.event_date),
                    r1=float(r1),
                    r2=float(r2),
                    r3=float(r3),
                    r4=float(r4),
                    rel1=rel_map.get(1),
                    rel2=rel_map.get(2),
                    rel3=rel_map.get(3),
                    rel4=rel_map.get(4),
                    imp1=float(i1),
                    imp2=float(i2),
                    imp3=float(i3),
                    imp4=float(i4),
                    games1=_games_from_team(t0),
                    games2=_games_from_team(t1),
                    winner=winner,
                    jon_slot=jon_slot,
                )
            )

    rows.sort(
        key=lambda m: (
            m.event_date is None,
            m.event_date or datetime.max.replace(tzinfo=timezone.utc),
            m.match_id,
        ),
        reverse=True,
    )
    rows = rows[:limit]
    rows.sort(
        key=lambda m: (
            m.event_date is None,
            m.event_date or datetime.max.replace(tzinfo=timezone.utc),
            m.match_id,
        )
    )
    coverage = {
        "matches_selected": len(rows),
        "skipped_missing_fields": skipped_missing_fields,
        "skipped_no_jon": skipped_no_jon,
        "reliability_points_present": reliability_points,
        "reliability_points_total": reliability_total,
        "reliability_coverage_pct": float(reliability_points / reliability_total * 100.0)
        if reliability_total
        else 0.0,
    }
    return rows, coverage


def evaluate(limit: int, model_file: str) -> Dict[str, Any]:
    matches, coverage = _load_jon_matches(limit=limit)
    if not matches:
        raise RuntimeError("No matches found for Jon with required pre/impact fields.")

    predictor = DuprPredictor(model_file)
    all_true: List[float] = []
    all_pred: List[float] = []
    jon_true: List[float] = []
    jon_pred: List[float] = []

    for m in matches:
        p1, p2, p3, p4 = predictor.predict_impacts(
            m.r1,
            m.r2,
            m.r3,
            m.r4,
            m.games1,
            m.games2,
            m.winner,
            rel1=m.rel1,
            rel2=m.rel2,
            rel3=m.rel3,
            rel4=m.rel4,
        )
        preds = [p1, p2, p3, p4]
        trues = [m.imp1, m.imp2, m.imp3, m.imp4]
        all_pred.extend(preds)
        all_true.extend(trues)
        jon_pred.append(preds[m.jon_slot - 1])
        jon_true.append(trues[m.jon_slot - 1])

    all_true_arr = np.array(all_true, dtype=float)
    all_pred_arr = np.array(all_pred, dtype=float)
    jon_true_arr = np.array(jon_true, dtype=float)
    jon_pred_arr = np.array(jon_pred, dtype=float)

    score_all = _score_metrics(all_true_arr, all_pred_arr)
    score_jon = _score_metrics(jon_true_arr, jon_pred_arr)
    grade_all = _grade_strict(score_all)
    grade_jon = _grade_strict(score_jon)
    overall_pass = bool(grade_all["pass"] and grade_jon["pass"])

    return {
        "config": {
            "model_file": model_file,
            "strict_thresholds": STRICT_THRESHOLDS,
            "limit_matches": limit,
        },
        "coverage": coverage,
        "scorecards": {
            "jon_only": {"metrics": score_jon, "grade": grade_jon},
            "all_players": {"metrics": score_all, "grade": grade_all},
        },
        "overall_strict_pass": overall_pass,
        "recommendation": (
            "trusted" if overall_pass else "caution"
            if (grade_jon["pass"] or grade_all["pass"])
            else "low_trust"
        ),
    }


def _print_scorecard(name: str, card: Dict[str, Any]) -> None:
    metrics = card["metrics"]
    grade = card["grade"]
    print(f"\n{name}")
    print("-" * 60)
    print(f"n_points: {metrics['n_points']}")
    print(f"MAE: {metrics['mae']:.6f} (target <= {STRICT_THRESHOLDS['mae_max']:.3f})")
    print(f"RMSE: {metrics['rmse']:.6f}")
    print(
        f"Pearson: {metrics['pearson']:.6f} "
        f"(target >= {STRICT_THRESHOLDS['pearson_min']:.2f})"
    )
    print(f"Spearman: {metrics['spearman']:.6f}")
    print(f"R^2: {metrics['r2']:.6f} (target >= {STRICT_THRESHOLDS['r2_min']:.2f})")
    print(f"Sign accuracy: {metrics['sign_accuracy']:.3%}")
    print(
        "Abs error p50/p90/p95: "
        f"{metrics['p50_abs_error']:.6f} / {metrics['p90_abs_error']:.6f} / {metrics['p95_abs_error']:.6f}"
    )
    print(f"STRICT PASS: {'YES' if grade['pass'] else 'NO'}")
    if not grade["pass"]:
        gaps = grade["gaps_to_target"]
        print(
            "Gaps -> "
            f"mae_over={gaps['mae_over']:.6f}, "
            f"pearson_under={gaps['pearson_under']:.6f}, "
            f"r2_under={gaps['r2_under']:.6f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate DuprPredictor accuracy on Jon's last matches from dupr.sqlite."
    )
    parser.add_argument("--limit", type=int, default=74, help="How many recent Jon matches.")
    parser.add_argument(
        "--model-file", default="dupr_model.json", help="Path to dupr model json."
    )
    parser.add_argument(
        "--json", action="store_true", help="Print only JSON output."
    )
    args = parser.parse_args()

    output = evaluate(limit=args.limit, model_file=args.model_file)
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0

    cov = output["coverage"]
    print("DUPR Predictor Confidence Evaluation")
    print("=" * 60)
    print(f"Matches selected: {cov['matches_selected']}")
    print(
        "Reliability coverage (player-points): "
        f"{cov['reliability_points_present']}/{cov['reliability_points_total']} "
        f"({cov['reliability_coverage_pct']:.2f}%)"
    )
    print(
        "Skipped rows -> "
        f"missing_fields={cov['skipped_missing_fields']}, "
        f"not_jon={cov['skipped_no_jon']}"
    )

    _print_scorecard("Jon-only scorecard", output["scorecards"]["jon_only"])
    _print_scorecard("All-player scorecard", output["scorecards"]["all_players"])

    print("\nOverall strict status")
    print("-" * 60)
    print(f"Overall strict pass: {'YES' if output['overall_strict_pass'] else 'NO'}")
    print(f"Recommendation for reset what-if usage: {output['recommendation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

