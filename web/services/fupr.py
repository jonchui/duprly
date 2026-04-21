"""
FUPR service — audience interpretation of a player's "true" rating.

Model:
- Anyone can submit a guess in [2.0, 7.0] with a confidence in [1, 5].
- One vote per (player, voter_key) — voter_key is an IP hash or signed-in id.
- Aggregate = confidence-weighted mean + median + histogram + count.

Confidence weighting means a voter who says 5/5 confidence counts more than
someone who says 1/5. Medians are unweighted.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from statistics import median
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from web.models import FuprVote

MIN_RATING = 2.0
MAX_RATING = 7.0


@dataclass
class FuprAggregate:
    player_id: int
    count: int
    weighted_mean: Optional[float]
    median: Optional[float]
    histogram: Dict[str, int]  # bucket label -> count


def _validate(rating: float, confidence: int) -> None:
    if not (MIN_RATING <= rating <= MAX_RATING):
        raise ValueError(f"rating must be between {MIN_RATING} and {MAX_RATING}")
    if not (1 <= confidence <= 5):
        raise ValueError("confidence must be between 1 and 5")


def hash_voter_key(raw: str) -> str:
    """Hash the raw voter key so we don't store raw IPs."""
    return sha256(raw.encode("utf-8")).hexdigest()[:40]


def cast_vote(
    session: Session,
    player_id: int,
    rating: float,
    confidence: int,
    voter_key: str,
    comment: Optional[str] = None,
) -> FuprVote:
    _validate(rating, confidence)
    hashed = hash_voter_key(voter_key)

    # Upsert-ish: try insert, fall back to update on conflict.
    existing = session.execute(
        select(FuprVote).where(
            FuprVote.jupr_player_id == player_id,
            FuprVote.voter_key == hashed,
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.rating = rating
        existing.confidence = confidence
        existing.comment = comment
        session.flush()
        return existing

    vote = FuprVote(
        jupr_player_id=player_id,
        rating=rating,
        confidence=confidence,
        voter_key=hashed,
        comment=comment,
    )
    session.add(vote)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        # Rare race; re-read.
        return session.execute(
            select(FuprVote).where(
                FuprVote.jupr_player_id == player_id,
                FuprVote.voter_key == hashed,
            )
        ).scalar_one()
    return vote


def _bucket(rating: float) -> str:
    # Half-point buckets: 2.0, 2.5, 3.0, ...
    b = round(rating * 2) / 2
    return f"{b:.1f}"


def aggregate(session: Session, player_id: int) -> FuprAggregate:
    votes: List[FuprVote] = list(
        session.execute(
            select(FuprVote).where(FuprVote.jupr_player_id == player_id)
        ).scalars().all()
    )
    if not votes:
        return FuprAggregate(
            player_id=player_id,
            count=0,
            weighted_mean=None,
            median=None,
            histogram={},
        )

    total_weight = sum(v.confidence for v in votes)
    weighted_mean = sum(v.rating * v.confidence for v in votes) / total_weight
    med = median([v.rating for v in votes])
    histogram: Dict[str, int] = {}
    for v in votes:
        label = _bucket(v.rating)
        histogram[label] = histogram.get(label, 0) + 1

    return FuprAggregate(
        player_id=player_id,
        count=len(votes),
        weighted_mean=weighted_mean,
        median=med,
        histogram=dict(sorted(histogram.items(), key=lambda kv: float(kv[0]))),
    )
