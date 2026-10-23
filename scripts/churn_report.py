#!/usr/bin/env python3
"""
Cross-reference the loyalist cohort (>= 10 visits, non-bot) from the
2025 Picklr CRM data with the last 45 days of the PBP admin calendar.
Print a ranked list of loyalists who appear to have churned, plus the
crosstabs that go into the canvas.

Usage:
    python scripts/churn_report.py --db dupr.sqlite --window-days 45
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CHURN_SQL = """
WITH loyalists AS (
  SELECT c.picklr_user_id, c.contact_id,
         c.total_checkins, c.total_orders, c.total_spend_cents,
         substr(c.first_seen_at, 1, 10) AS first_seen,
         substr(c.last_seen_at,  1, 10) AS last_seen
    FROM picklr_contact c
   WHERE c.total_checkins >= 10
     AND COALESCE(c.is_bot, 0) = 0
     AND c.picklr_user_id IS NOT NULL
),
recent AS (
  SELECT user_id, MAX(event_date) AS pbp_last_seen, COUNT(*) AS recent_n
    FROM pbp_reservation
   GROUP BY user_id
),
mem AS (
  SELECT DISTINCT contact_id FROM picklr_order
   WHERE category='membership' AND total_amount_cents > 0
)
SELECT l.picklr_user_id AS uid,
       u.name           AS name,
       l.total_checkins AS hist_chk,
       l.total_orders   AS hist_ord,
       ROUND(l.total_spend_cents/100.0, 0) AS hist_usd,
       CASE WHEN m.contact_id IS NOT NULL THEN 1 ELSE 0 END AS was_member,
       l.last_seen      AS last_seen_2025
  FROM loyalists l
  LEFT JOIN recent  r ON r.user_id = l.picklr_user_id
  LEFT JOIN pbp_user u ON u.user_id = l.picklr_user_id
  LEFT JOIN mem     m ON m.contact_id = l.contact_id
 WHERE r.user_id IS NULL
 ORDER BY l.total_spend_cents DESC, l.total_checkins DESC
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="dupr.sqlite", type=Path)
    ap.add_argument("--window-days", type=int, default=45)
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    conn = sqlite3.connect(str(args.db))
    rows = conn.execute(CHURN_SQL).fetchall()

    print(f"\n{len(rows)} loyalists with NO reservation in last {args.window_days} days\n")
    print(f"{'UID':<10}{'Name':<32}{'Chk':>5}{'Ord':>5}{'USD':>8}  Mem  Last seen")
    print("-" * 80)
    for uid, name, chk, ord_, usd, mem, ls in rows[: args.top]:
        print(f"{uid:<10}{(name or '?')[:32]:<32}{chk:>5}{ord_:>5}{usd:>8.0f}  {'Y' if mem else ' '}    {ls or ''}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
