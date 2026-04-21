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


def _is_bad_name(name: Optional[str]) -> bool:
    """Reject names like '', 'undefined undefined', 'null', 'None None' etc."""
    if not name:
        return True
    n = name.strip().lower()
    if not n:
        return True
    tokens = [t for t in n.split() if t]
    bad_tokens = {"undefined", "null", "none", "nil", "nan"}
    # If *every* token is a sentinel/literal-null, reject.
    return bool(tokens) and all(t in bad_tokens for t in tokens)


def upsert_cached_player(session: Session, hit: Dict[str, Any]) -> Optional[DuprCachedPlayer]:
    """Create/update a DuprCachedPlayer row from a DUPR API hit dict."""
    dupr_id = hit.get("id") or hit.get("userId")
    if dupr_id is None:
        return None
    dupr_id = str(dupr_id)

    ratings = _extract_ratings(hit)

    def _clean_str(v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        if not s or s.lower() in {"undefined", "null", "none", "nil", "nan"}:
            return None
        return s

    first_name = _clean_str(hit.get("firstName"))
    last_name = _clean_str(hit.get("lastName"))
    full_name = _clean_str(hit.get("fullName")) or " ".join(
        x for x in [first_name, last_name] if x
    ).strip()
    if _is_bad_name(full_name):
        _LOG.info("skip cache upsert for id=%s: bad name %r", dupr_id, full_name)
        return None

    short_address = _clean_str(hit.get("shortAddress") or hit.get("shortAddress".lower()))

    existing = session.get(DuprCachedPlayer, dupr_id)
    now = datetime.now(timezone.utc)
    if existing is None:
        row = DuprCachedPlayer(
            dupr_id=dupr_id,
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            short_dupr_id=_clean_str(hit.get("duprId")),
            doubles=ratings.get("doubles"),
            doubles_reliability=ratings.get("doubles_reliability"),
            doubles_verified=ratings.get("doubles_verified", False),
            singles=ratings.get("singles"),
            singles_reliability=ratings.get("singles_reliability"),
            singles_verified=ratings.get("singles_verified", False),
            image_url=hit.get("imageUrl"),
            gender=_clean_str(hit.get("gender")),
            age=hit.get("age"),
            short_address=short_address,
            last_synced_at=now,
        )
        session.add(row)
        session.flush()
        return row

    existing.full_name = full_name
    existing.first_name = first_name or existing.first_name
    existing.last_name = last_name or existing.last_name
    existing.short_dupr_id = _clean_str(hit.get("duprId")) or existing.short_dupr_id
    for field in (
        "doubles", "doubles_reliability", "doubles_verified",
        "singles", "singles_reliability", "singles_verified",
    ):
        v = ratings.get(field)
        if v is not None:
            setattr(existing, field, v)
    if hit.get("imageUrl"):
        existing.image_url = hit["imageUrl"]
    if _clean_str(hit.get("gender")):
        existing.gender = _clean_str(hit.get("gender"))
    if hit.get("age") is not None:
        existing.age = hit["age"]
    if short_address:
        existing.short_address = short_address
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
    # Richer metadata used by the DUPR-style match card (age · M · location).
    age: Optional[int] = None
    gender: Optional[str] = None
    short_address: Optional[str] = None
    short_dupr_id: Optional[str] = None


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
        age=row.age,
        gender=row.gender,
        short_address=row.short_address,
        short_dupr_id=row.short_dupr_id,
    )


import re as _re

_SHORT_ID_RE = _re.compile(r"^[A-Z0-9]{6}$")
_NUMERIC_ID_RE = _re.compile(r"^\d{6,}$")
# Matches `https://dashboard.dupr.com/dashboard/player/4405492894` and friends:
# allow any dupr.com host, any path, so long as /player/<digits> appears.
_DUPR_URL_ID_RE = _re.compile(
    r"(?:https?://)?(?:\w+\.)*dupr\.com/[^\s?#]*?/player/(\d+)",
    _re.IGNORECASE,
)


def _looks_like_short_id(q: str) -> bool:
    return bool(_SHORT_ID_RE.match(q.upper()))


def _looks_like_numeric_id(q: str) -> bool:
    return bool(_NUMERIC_ID_RE.match(q))


def _extract_numeric_id_from_url(q: str) -> Optional[str]:
    """Return the numeric DUPR id if `q` is a dashboard.dupr.com player URL."""
    m = _DUPR_URL_ID_RE.search(q)
    return m.group(1) if m else None


def search(
    session: Session,
    query: str,
    limit: int = 15,
    live_fallback: bool = True,
) -> List[PlayerSearchHit]:
    """
    Hybrid search: cache first, live DUPR fallback when results look thin or
    when the query looks like a DUPR id (6-char alphanumeric short id, or a
    long numeric internal id).
    """
    q = (query or "").strip()
    if not q:
        return []

    # If the user pastes a dashboard URL like
    #   https://dashboard.dupr.com/dashboard/player/4405492894
    # normalize to the numeric id. This is the *only* reliable way to hit
    # profiles with shortAddress=null — DUPR's /search silently drops them.
    url_id = _extract_numeric_id_from_url(q)
    if url_id:
        q = url_id

    is_short_id = _looks_like_short_id(q)
    is_numeric_id = _looks_like_numeric_id(q)

    # Cache search: ILIKE on name + exact match on short DUPR id + numeric id.
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

    # Force live fallback whenever the cache is thin OR the query smells like
    # an exact-lookup (short/numeric DUPR id). Previously we gated live fallback
    # behind `(" " in q and len(hits) < 5)` for multi-word queries, which meant
    # single-word searches like "bryan" would silently stop at a stale cache
    # result and never surface fresh DUPR hits (e.g. "Bryan Sullivan"). The
    # fix: live-fallback any time the cache returned fewer hits than the
    # requested limit (capped at 5 so we're not hammering DUPR for every
    # incidental keystroke).
    id_shape = is_short_id or is_numeric_id
    thin_cache_threshold = min(5, limit)
    thin_cache = len(hits) < thin_cache_threshold or id_shape

    if live_fallback and thin_cache and _has_live_credentials():
        try:
            client = _get_live_client()

            # If it looks like a numeric id, try the exact-player endpoint first.
            if is_numeric_id:
                try:
                    rc, player = client.get_player(q)
                    if rc == 200 and isinstance(player, dict):
                        row = upsert_cached_player(session, player)
                        if row is not None and not any(h.dupr_id == row.dupr_id for h in hits):
                            h = _cached_to_hit(row)
                            h.source = "live"
                            hits.append(h)
                except Exception as exc:
                    _LOG.warning("dupr get_player failed id=%r err=%s", q, exc)

            # Name search / short-id search (DUPR's /search endpoint accepts both).
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
                            if not any(h.dupr_id == row.dupr_id for h in hits):
                                h = _cached_to_hit(row)
                                h.source = "live"
                                hits.append(h)
        except Exception as exc:
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
