"""
Court rosters for the pckl.bot app.

The app reads who's in a class from the venue (e.g. Relish on CourtReserve shows
"Cindy S."), then asks here for each name's DUPR (if someone linked it), crowd
skill (FUPR) and the asker's own "play again" vote. After a class, players vote.

Voters are identified by a hash of their pckl.bot email, never the raw email.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from statistics import median
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from web.models import CourtPerson, CourtVote, DuprCachedPlayer

MIN_SKILL, MAX_SKILL = 2.0, 7.0
MAX_NAMES = 40


def voter_hash(email: str) -> str:
    e = (email or "").strip().lower()
    if "@" not in e:
        raise ValueError("voter must be an email")
    return sha256(e.encode("utf-8")).hexdigest()[:40]


def _clean(name: str) -> str:
    return " ".join((name or "").split())[:128]


def _person(session: Session, venue: str, name: str, create: bool = True) -> Optional[CourtPerson]:
    name = _clean(name)
    if not name:
        return None
    p = session.execute(select(CourtPerson).where(CourtPerson.venue == venue, CourtPerson.name == name)).scalar_one_or_none()
    if p is None and create:
        p = CourtPerson(venue=venue, name=name)
        session.add(p)
        session.flush()
    return p


def _dupr(session: Session, dupr_id: Optional[str]) -> Optional[Dict]:
    if not dupr_id:
        return None
    row = session.get(DuprCachedPlayer, dupr_id)
    if row is None:
        return {"dupr_id": dupr_id, "full_name": None, "doubles": None, "image_url": None}
    return {"dupr_id": row.dupr_id, "full_name": row.full_name, "doubles": row.doubles, "image_url": row.image_url}


def people(session: Session, venue: str, names: List[str], voter: str) -> List[Dict]:
    me = voter_hash(voter)
    out = []
    for raw in names[:MAX_NAMES]:
        p = _person(session, venue, raw)
        if p is None:
            continue
        votes = session.execute(select(CourtVote).where(CourtVote.person_id == p.id)).scalars().all()
        skills = [v.skill for v in votes if v.skill is not None]
        mine = [v for v in votes if v.voter_key == me]
        latest = max(mine, key=lambda v: v.updated_at) if mine else None
        out.append({
            "name": p.name,
            "dupr": _dupr(session, p.dupr_id),
            "fupr": {"count": len(skills), "median": round(median(skills), 2) if skills else None},
            "mine": {"skill": latest.skill, "again": latest.again} if latest else None,
        })
    return out


def link(session: Session, venue: str, name: str, dupr_id: Optional[str], voter: str) -> Dict:
    me = voter_hash(voter)
    if dupr_id and session.get(DuprCachedPlayer, dupr_id) is None:
        raise ValueError("unknown DUPR id — search for the player first")
    p = _person(session, venue, name)
    if p is None:
        raise ValueError("name is required")
    p.dupr_id = dupr_id or None
    p.linked_by = me
    p.updated_at = datetime.now(timezone.utc)
    return {"name": p.name, "dupr": _dupr(session, p.dupr_id)}


def vote(session: Session, venue: str, class_id: str, voter: str, votes: List[Dict]) -> int:
    me = voter_hash(voter)
    if not class_id:
        raise ValueError("class_id is required")
    n = 0
    for v in votes[:MAX_NAMES]:
        skill, again = v.get("skill"), v.get("again")
        if skill is not None and not (MIN_SKILL <= float(skill) <= MAX_SKILL):
            raise ValueError(f"skill must be between {MIN_SKILL} and {MAX_SKILL}")
        if again not in (None, 1, -1):
            raise ValueError("again must be 1, -1 or null")
        p = _person(session, venue, v.get("name", ""))
        if p is None:
            continue
        row = session.execute(select(CourtVote).where(
            CourtVote.person_id == p.id, CourtVote.voter_key == me, CourtVote.class_id == class_id,
        )).scalar_one_or_none()
        if row is None:
            row = CourtVote(person_id=p.id, voter_key=me, class_id=class_id)
            session.add(row)
        row.skill = None if skill is None else round(float(skill), 2)
        row.again = again
        row.updated_at = datetime.now(timezone.utc)
        n += 1
    return n
