#!/usr/bin/env python3
"""
Seed the web app's DuprCachedPlayer table from the existing dupr.sqlite crawl.

Usage:
    python3 scripts/seed_cached_players.py [--limit N] [--source dupr.sqlite] [--dest DATABASE_URL]

Run this locally before `uvicorn` so the forecast page's player search has
real data to show without needing DUPR API credentials.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="sqlite+pysqlite:///dupr.sqlite")
    parser.add_argument(
        "--dest",
        default=os.environ.get("DATABASE_URL"),
        help="Destination DATABASE_URL (defaults to local duprly_web.db)",
    )
    parser.add_argument("--limit", type=int, default=0, help="Cap on players to seed (0 = all)")
    args = parser.parse_args()

    from dupr_db import Player  # source schema
    from web.db import get_engine, init_db
    from web.models import DuprCachedPlayer

    if args.dest:
        os.environ["DATABASE_URL"] = args.dest

    init_db()
    dest_engine = get_engine()
    DestSession = sessionmaker(bind=dest_engine, autoflush=False, autocommit=False)

    src_engine = create_engine(args.source, echo=False)
    SrcSession = sessionmaker(bind=src_engine, autoflush=False, autocommit=False)

    imported = 0
    skipped = 0
    now = datetime.now(timezone.utc)

    with SrcSession() as src, DestSession() as dest:
        players = list(src.execute(select(Player)).scalars().all())
        if args.limit:
            players = players[: args.limit]

        for p in players:
            dupr_id = str(p.dupr_id) if p.dupr_id is not None else None
            if not dupr_id:
                skipped += 1
                continue
            full_name = (p.full_name or "").strip()
            if not full_name:
                skipped += 1
                continue

            existing = dest.get(DuprCachedPlayer, dupr_id)
            rating = p.rating  # relationship
            doubles = rating.doubles_verified or rating.doubles if rating else None
            singles = rating.singles_verified or rating.singles if rating else None

            if existing is None:
                dest.add(
                    DuprCachedPlayer(
                        dupr_id=dupr_id,
                        full_name=full_name,
                        first_name=p.first_name,
                        last_name=p.last_name,
                        doubles=float(doubles) if doubles is not None else None,
                        singles=float(singles) if singles is not None else None,
                        doubles_verified=bool(rating and not rating.is_doubles_provisional) if rating else False,
                        singles_verified=bool(rating and not rating.is_singles_provisional) if rating else False,
                        image_url=p.image_url,
                        gender=p.gender,
                        age=p.age,
                        last_synced_at=now,
                    )
                )
            else:
                existing.full_name = full_name
                if doubles is not None:
                    existing.doubles = float(doubles)
                if singles is not None:
                    existing.singles = float(singles)
                existing.image_url = p.image_url or existing.image_url
                existing.gender = p.gender or existing.gender
                if p.age is not None:
                    existing.age = p.age
                existing.last_synced_at = now
            imported += 1

        dest.commit()

    print(f"Seeded {imported} players into DuprCachedPlayer (skipped {skipped}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
