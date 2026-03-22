#!/usr/bin/env python3
"""
SQLite persistence for shadow reset runs.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS shadow_reset_runs (
            run_id TEXT PRIMARY KEY,
            run_at_utc TEXT NOT NULL,
            player_id TEXT NOT NULL,
            player_name TEXT,
            requested_dupr_id TEXT,
            mode TEXT NOT NULL,
            windows_csv TEXT NOT NULL,
            baseline_rating REAL,
            current_reliability REAL,
            total_usable_matches INTEGER,
            raw_payload_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS shadow_reset_window_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            window_size INTEGER NOT NULL,
            matches_considered INTEGER,
            matches_used INTEGER,
            matches_skipped INTEGER,
            baseline_rating REAL,
            shadow_rating REAL,
            delta REAL,
            higher_of_rating REAL,
            partner_diversity INTEGER,
            opponent_diversity INTEGER,
            qualifies_reset_style INTEGER,
            skip_reasons_json TEXT,
            FOREIGN KEY (run_id) REFERENCES shadow_reset_runs(run_id)
        )
        """
    )
    conn.commit()


def persist_shadow_run(
    payload: Dict[str, Any],
    player_name: Optional[str],
    requested_dupr_id: str,
    baseline_rating: Optional[float],
    current_reliability: Optional[float],
    db_path: Optional[str] = None,
) -> str:
    out_path = Path(db_path) if db_path else Path("shadow_reset_history.db")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    run_id = str(uuid.uuid4())
    windows = payload.get("windows", [])
    windows_csv = ",".join(str(w) for w in windows)
    total_usable = payload.get("total_player_matches_available")

    conn = sqlite3.connect(str(out_path))
    try:
        _ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO shadow_reset_runs (
                run_id, run_at_utc, player_id, player_name, requested_dupr_id, mode,
                windows_csv, baseline_rating, current_reliability, total_usable_matches,
                raw_payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                _utc_now_iso(),
                str(payload.get("player_id", "")),
                player_name,
                str(requested_dupr_id),
                str(payload.get("mode", "")),
                windows_csv,
                baseline_rating,
                current_reliability,
                int(total_usable) if total_usable is not None else None,
                json.dumps(payload),
            ),
        )

        results = payload.get("results", {})
        for window in windows:
            row = results.get(str(window), {})
            conn.execute(
                """
                INSERT INTO shadow_reset_window_results (
                    run_id, window_size, matches_considered, matches_used, matches_skipped,
                    baseline_rating, shadow_rating, delta, higher_of_rating,
                    partner_diversity, opponent_diversity, qualifies_reset_style, skip_reasons_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    int(window),
                    row.get("matches_considered"),
                    row.get("matches_used"),
                    row.get("matches_skipped"),
                    row.get("baseline_rating"),
                    row.get("shadow_rating"),
                    row.get("delta"),
                    row.get("higher_of_rating"),
                    row.get("partner_diversity"),
                    row.get("opponent_diversity"),
                    1 if row.get("qualifies_reset_style") else 0,
                    json.dumps(row.get("skip_reasons", {})),
                ),
            )
        conn.commit()
    finally:
        conn.close()

    return run_id

