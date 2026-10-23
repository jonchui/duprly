#!/usr/bin/env python3
"""
Ingest `get_facility_courts_reservations` MCP responses into SQLite.

The companion `data/pbp_calendar/` directory holds one JSON file per day
named `YYYY-MM-DD.json` — the raw payload the courts MCP returns for that
date.  This script flattens each payload into rows on `pbp_reservation`
(one per reservation/clinic) and `pbp_user` (one per primary holder seen).

It is used by the churn detector to compare against the loyalist cohort
in `picklr_contact`.  Both tables live in `dupr.sqlite` so they join
cleanly with the existing `picklr_*` schema via `picklr_user_id`.

Usage:
    python scripts/import_pbp_calendar.py \
        --dir data/pbp_calendar \
        --db  dupr.sqlite

Re-runs are idempotent: rows are upserted by reservation id + date.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Optional


DDL = """
CREATE TABLE IF NOT EXISTS pbp_user (
    user_id      INTEGER PRIMARY KEY,
    name         TEXT,
    is_bot       INTEGER DEFAULT 0,   -- ball machines, "Guest" shared accounts
    first_seen   TEXT,
    last_seen    TEXT
);

CREATE TABLE IF NOT EXISTS pbp_reservation (
    id              TEXT PRIMARY KEY,       -- e.g. "RES44EBF643CA"
    facility_id     INTEGER,
    court_id        INTEGER,
    court_name      TEXT,
    event_date      TEXT NOT NULL,          -- YYYY-MM-DD (facility-local)
    hour_start      INTEGER,                -- seconds from midnight
    hour_end        INTEGER,
    kind            TEXT,                   -- reservation, clinic, lesson, ...
    subkind         TEXT,
    status          TEXT,
    extended_status TEXT,                   -- "checked in", "no_show", ...
    user_id         INTEGER,                -- primary holder
    user_name       TEXT,
    teacher_name    TEXT,
    capacity        INTEGER,
    player_count    INTEGER,
    clinic_lesson_id INTEGER,
    clinic_capacity INTEGER,
    clinic_player_count INTEGER,
    admin_booked    INTEGER,
    raw_json        TEXT
);
CREATE INDEX IF NOT EXISTS ix_pbp_res_date  ON pbp_reservation(event_date);
CREATE INDEX IF NOT EXISTS ix_pbp_res_user  ON pbp_reservation(user_id);
CREATE INDEX IF NOT EXISTS ix_pbp_res_court ON pbp_reservation(court_id);
CREATE INDEX IF NOT EXISTS ix_pbp_res_kind  ON pbp_reservation(kind);
"""

# Known bot/equipment accounts at Thornton (extend as we discover more).
KNOWN_BOTS: dict[int, str] = {
    1737914: "Thornton CO #1 Erne Ball Machine",
    1751348: "Thornton CO #2 (OUT OF COMMISSION) Erne Ball Machine",
    1897300: "Guest",
}


def upsert_user(conn: sqlite3.Connection, uid: int, name: Optional[str], event_date: str) -> None:
    if uid is None:
        return
    is_bot = 1 if uid in KNOWN_BOTS or (name and is_bot_name(name)) else 0
    conn.execute(
        """INSERT INTO pbp_user(user_id, name, is_bot, first_seen, last_seen)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(user_id) DO UPDATE SET
              name       = COALESCE(excluded.name, pbp_user.name),
              is_bot     = MAX(pbp_user.is_bot, excluded.is_bot),
              first_seen = MIN(COALESCE(pbp_user.first_seen, excluded.first_seen),
                               excluded.first_seen),
              last_seen  = MAX(COALESCE(pbp_user.last_seen, excluded.last_seen),
                               excluded.last_seen)""",
        (uid, name, is_bot, event_date, event_date),
    )


def is_bot_name(name: str) -> bool:
    n = name.lower()
    return any(needle in n for needle in (
        "ball machine",
        "front desk",
        "guest ",
        "tester",
        "(test)",
        "(staff)",
    )) or n.strip() == "guest"


def process_day(conn: sqlite3.Connection, payload: dict[str, Any]) -> int:
    facility_id = payload.get("facility_id")
    date_str = payload.get("date")
    if not date_str:
        return 0
    n = 0
    for court in payload.get("courts_with_reservations", []) or []:
        court_id = court.get("id")
        court_name = court.get("name")
        for r in court.get("reservations", []) or []:
            user = r.get("user") or {}
            uid = user.get("id")
            uname = user.get("name")
            upsert_user(conn, uid, uname, date_str)

            conn.execute(
                """INSERT OR REPLACE INTO pbp_reservation(
                     id, facility_id, court_id, court_name, event_date,
                     hour_start, hour_end, kind, subkind, status, extended_status,
                     user_id, user_name, teacher_name,
                     capacity, player_count,
                     clinic_lesson_id, clinic_capacity, clinic_player_count,
                     admin_booked, raw_json
                   ) VALUES (?, ?, ?, ?, ?,
                             ?, ?, ?, ?, ?, ?,
                             ?, ?, ?,
                             ?, ?,
                             ?, ?, ?,
                             ?, ?)""",
                (
                    r.get("id"), facility_id, court_id, court_name, date_str,
                    r.get("hour_start"), r.get("hour_end"),
                    r.get("kind"), r.get("subkind"),
                    r.get("status"), r.get("extended_status"),
                    uid, uname, r.get("teacher"),
                    r.get("reservation_capacity"), r.get("reservation_player_count"),
                    r.get("clinic_lesson_id"), r.get("clinic_lesson_capacity"),
                    r.get("clinic_lesson_player_count"),
                    1 if r.get("admin_booked") else 0,
                    json.dumps(r, separators=(",", ":")),
                ),
            )
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default="data/pbp_calendar", type=Path)
    ap.add_argument("--db",  default="dupr.sqlite",        type=Path)
    args = ap.parse_args()

    if not args.dir.exists():
        print(f"ERROR: {args.dir} not found", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(args.db))
    conn.executescript(DDL)

    files = sorted(args.dir.glob("*.json"))
    if not files:
        print(f"No .json files found in {args.dir}")
        return 0

    grand_total = 0
    for f in files:
        try:
            payload = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            print(f"  skip {f.name}: {e}", file=sys.stderr)
            continue
        n = process_day(conn, payload)
        grand_total += n
        print(f"  {f.name}: {n} reservations")

    # Mirror the bot flag onto picklr_contact so analytics can exclude them.
    conn.execute("""
        UPDATE picklr_contact
           SET dupr_player_id = dupr_player_id   -- noop, schema warmup
    """)
    # Add an `is_bot` column on picklr_contact if missing (sqlite-safe).
    cols = {r[1] for r in conn.execute("PRAGMA table_info(picklr_contact)")}
    if "is_bot" not in cols:
        conn.execute("ALTER TABLE picklr_contact ADD COLUMN is_bot INTEGER DEFAULT 0")
    conn.execute("""
        UPDATE picklr_contact
           SET is_bot = 1
         WHERE picklr_user_id IN (SELECT user_id FROM pbp_user WHERE is_bot = 1)
    """)

    conn.commit()
    conn.close()
    print(f"\nTotal: {grand_total:,} reservations across {len(files)} days")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
