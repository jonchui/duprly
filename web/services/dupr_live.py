"""
Hybrid DUPR player lookup.

Reads from our local Postgres/SQLite cache (DuprCachedPlayer) first for speed
and offline friendliness. Optionally falls back to the live DUPR API using
`dupr_client.DuprClient` when credentials are configured via environment:

  DUPR_USERNAME, DUPR_PASSWORD

On a successful live fetch, we upsert into the cache so subsequent searches
don't need to hit DUPR again.

This module is intentionally lazy — the `dupr_client` import happens inside
the function body so the web app can boot on Vercel even when DUPR creds are
absent (e.g. initial deploy).
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from web.models import DuprCachedPlayer

_LOG = logging.getLogger("duprly.dupr_live")
_CLIENT_LOCK = threading.Lock()
_CLIENT_SINGLETON: Any | None = None


def _has_live_credentials() -> bool:
    return bool(os.environ.get("DUPR_USERNAME") and os.environ.get("DUPR_PASSWORD"))


def _get_live_client():
    """Return a memoized authenticated DuprClient, or raise if not configured."""
    global _CLIENT_SINGLETON
    if not _has_live_credentials():
        raise RuntimeError(
            "DUPR live lookup not configured — set DUPR_USERNAME and DUPR_PASSWORD"
        )
    with _CLIENT_LOCK:
        if _CLIENT_SINGLETON is None:
            from dupr_client import DuprClient  # imported lazily
            c = DuprClient()
            rc = c.auth_user(
                os.environ["DUPR_USERNAME"],
                os.environ["DUPR_PASSWORD"],
            )
            if rc != 0 and rc != 200:
                raise RuntimeError(f"DUPR auth failed ({rc})")
            _CLIENT_SINGLETON = c
    return _CLIENT_SINGLETON


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s or s.upper() == "NR":
            return None
        try:
            return float(s)
        except ValueError:
            return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _extract_ratings(hit: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize the API's many rating-shape variants into a flat dict."""
    r: Dict[str, Any] = {}
    ratings = hit.get("ratings") if isinstance(hit.get("ratings"), dict) else hit

    for d_key in ("doubles", "doublesRating"):
        val = _safe_float(ratings.get(d_key) if ratings else hit.get(d_key))
        if val is not None:
            r["doubles"] = val
            break
    for s_key in ("singles", "singlesRating"):
        val = _safe_float(ratings.get(s_key) if ratings else hit.get(s_key))
        if val is not None:
            r["singles"] = val
            break

    r["doubles_reliability"] = _safe_float(
        (ratings.get("doublesReliabilityScore") if ratings else None)
        or (ratings.get("doublesReliability") if ratings else None)
        or hit.get("doublesReliabilityScore")
    )
    r["singles_reliability"] = _safe_float(
        (ratings.get("singlesReliabilityScore") if ratings else None)
        or (ratings.get("singlesReliability") if ratings else None)
        or hit.get("singlesReliabilityScore")
    )
    r["doubles_verified"] = bool(
        (ratings.get("isDoublesVerified") if ratings else None)
        or hit.get("isDoublesVerified")
        or (not (ratings.get("doublesProvisional") if ratings else True))
    )
    r["singles_verified"] = bool(
        (ratings.get("isSinglesVerified") if ratings else None)
        or hit.get("isSinglesVerified")
    )
    return r


def upsert_cached_player(session: Session, hit: Dict[str, Any]) -> Optional[DuprCachedPlayer]:
    """Create/update a DuprCachedPlayer row from a DUPR API hit dict."""
    dupr_id = hit.get("id") or hit.get("userId")
    if dupr_id is None:
        return None
    dupr_id = str(dupr_id)

    ratings = _extract_ratings(hit)

    full_name = hit.get("fullName") or " ".join(
        x for x in [hit.get("firstName"), hit.get("lastName")] if x
    ).strip()
    if not full_name:
        return None

    existing = session.get(DuprCachedPlayer, dupr_id)
    now = datetime.now(timezone.utc)
    if existing is None:
        row = DuprCachedPlayer(
            dupr_id=dupr_id,
            full_name=full_name,
            first_name=hit.get("firstName"),
            last_name=hit.get("lastName"),
            short_dupr_id=hit.get("duprId"),
            doubles=ratings.get("doubles"),
            doubles_reliability=ratings.get("doubles_reliability"),
            doubles_verified=ratings.get("doubles_verified", False),
            singles=ratings.get("singles"),
            singles_reliability=ratings.get("singles_reliability"),
            singles_verified=ratings.get("singles_verified", False),
            image_url=hit.get("imageUrl"),
            gender=hit.get("gender"),
            age=hit.get("age"),
            last_synced_at=now,
        )
        session.add(row)
        session.flush()
        return row

    # Update mutable fields
    existing.full_name = full_name
    existing.first_name = hit.get("firstName") or existing.first_name
    existing.last_name = hit.get("lastName") or existing.last_name
    existing.short_dupr_id = hit.get("duprId") or existing.short_dupr_id
    for field in (
        "doubles", "doubles_reliability", "doubles_verified",
        "singles", "singles_reliability", "singles_verified",
    ):
        v = ratings.get(field)
        if v is not None:
            setattr(existing, field, v)
    if hit.get("imageUrl"):
        existing.image_url = hit["imageUrl"]
    if hit.get("gender"):
        existing.gender = hit["gender"]
    if hit.get("age") is not None:
        existing.age = hit["age"]
    existing.last_synced_at = now
    session.flush()
    return existing


@dataclass
class PlayerSearchHit:
    dupr_id: str
    full_name: str
    doubles: Optional[float]
    doubles_reliability: Optional[float]
    singles: Optional[float]
    image_url: Optional[str]
    source: str  # "cache" or "live"
    stale: bool  # true if the cache entry is > CACHE_TTL_DAYS old


CACHE_TTL_DAYS = 30


def _cached_to_hit(row: DuprCachedPlayer) -> PlayerSearchHit:
    age_days = (datetime.now(timezone.utc) - row.last_synced_at.replace(tzinfo=timezone.utc)).days
    return PlayerSearchHit(
        dupr_id=row.dupr_id,
        full_name=row.full_name,
        doubles=row.doubles,
        doubles_reliability=row.doubles_reliability,
        singles=row.singles,
        image_url=row.image_url,
        source="cache",
        stale=age_days > CACHE_TTL_DAYS,
    )


def search(
    session: Session,
    query: str,
    limit: int = 15,
    live_fallback: bool = True,
) -> List[PlayerSearchHit]:
    """
    Search the cache first. If there's a clear signal the cache doesn't cover
    this query (few hits, short-duprId exact lookup misses, etc.) and live
    credentials are present, also hit the DUPR API and upsert the results.
    """
    q = (query or "").strip()
    if not q:
        return []

    # Cache search: ILIKE on name + exact match on short DUPR id.
    cache_rows = session.execute(
        select(DuprCachedPlayer)
        .where(
            or_(
                DuprCachedPlayer.full_name.ilike(f"%{q}%"),
                DuprCachedPlayer.short_dupr_id.ilike(q),
                DuprCachedPlayer.dupr_id == q,
            )
        )
        .order_by(DuprCachedPlayer.full_name)
        .limit(limit)
    ).scalars().all()
    hits: List[PlayerSearchHit] = [_cached_to_hit(r) for r in cache_rows]

    # Live fallback: fire if requested + creds exist + cache is "thin".
    # "Thin" = 0 hits, OR user typed a likely-full-name (has a space) and
    # we have fewer than 5 results from cache.
    thin_cache = (
        len(hits) == 0
        or (" " in q and len(hits) < 5)
    )
    if live_fallback and thin_cache and _has_live_credentials():
        try:
            client = _get_live_client()
            rc, result = client.search_players(q, limit=limit)
            _LOG.info("dupr live search q=%r rc=%s", q, rc)
            if rc == 200 and result:
                raw_hits = result.get("hits") if isinstance(result, dict) else result
                if isinstance(raw_hits, list):
                    for raw in raw_hits:
                        if not isinstance(raw, dict):
                            continue
                        row = upsert_cached_player(session, raw)
                        if row is not None:
                            # Avoid duplicating if already in `hits`.
                            if not any(h.dupr_id == row.dupr_id for h in hits):
                                h = _cached_to_hit(row)
                                h.source = "live"
                                hits.append(h)
        except Exception as exc:
            # We intentionally swallow — cache is the source of truth, live is best-effort.
            _LOG.warning("dupr live search failed q=%r err=%s", q, exc)
    elif live_fallback and thin_cache and not _has_live_credentials():
        _LOG.debug("dupr live search skipped (no DUPR_USERNAME/PASSWORD set)")

    return hits[:limit]


def refresh(session: Session, dupr_id: str) -> Optional[PlayerSearchHit]:
    """Force-refresh a single player from live DUPR and upsert into cache."""
    if not _has_live_credentials():
        raise RuntimeError("DUPR live lookup not configured")
    client = _get_live_client()
    rc, player = client.get_player(str(dupr_id))
    if rc != 200 or not player:
        return None
    row = upsert_cached_player(session, player)
    if row is None:
        return None
    return _cached_to_hit(row)


def get_by_id(session: Session, dupr_id: str) -> Optional[PlayerSearchHit]:
    row = session.get(DuprCachedPlayer, str(dupr_id))
    if row is None:
        return None
    return _cached_to_hit(row)
