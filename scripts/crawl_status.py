#!/usr/bin/env python3
"""
Print crawler status from the local DB (match counts, recent activity).
Run on the VPS: /root/duprly/.venv/bin/python scripts/crawl_status.py
Or from repo root: python scripts/crawl_status.py
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dupr_db import open_db, ClubMatchRaw
from sqlalchemy.orm import Session
from sqlalchemy import select, func

def main():
    eng = open_db()
    with Session(eng) as sess:
        total = sess.execute(select(func.count(ClubMatchRaw.id))).scalar() or 0
        print(f"Total club matches in DB: {total}")

        if total == 0:
            print("No matches yet. Is the crawler running? Check: systemctl status duprly-crawler")
            return

        # Most recently ingested matches
        recent = sess.execute(
            select(ClubMatchRaw)
            .order_by(ClubMatchRaw.created_at.desc())
            .limit(10)
        ).scalars().all()

        print(f"\nLast 10 matches ingested (most recent first):")
        print("-" * 60)
        for r in recent:
            ts = r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "?"
            print(f"  match_id={r.match_id}  event_date={r.event_date or '?'}  ingested={ts}")

        # Optional: count by event_date
        by_date = sess.execute(
            select(ClubMatchRaw.event_date, func.count(ClubMatchRaw.id))
            .where(ClubMatchRaw.event_date != None)
            .group_by(ClubMatchRaw.event_date)
            .order_by(ClubMatchRaw.event_date.desc())
            .limit(10)
        ).all()
        if by_date:
            print(f"\nMatches by event date (last 10 dates):")
            for d, c in by_date:
                print(f"  {d}: {c} matches")

if __name__ == "__main__":
    main()
