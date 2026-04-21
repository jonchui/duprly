"""
SQLAlchemy models for JUPR (our DUPR mirror) and FUPR (audience votes).

Design notes:
- JuprPlayer is the local identity. It may optionally link to a DUPR id.
- JuprGame stores one match (4 players, up to 3 games). We replay *JUPR games only*
  through the fitted DuprPredictor to compute current JUPR rating for any player.
- FuprVote is a crowd-sourced rating guess (2.0-7.0) for a player.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JuprPlayer(Base):
    """A player in our local JUPR mirror. Optionally linked to a DUPR id."""

    __tablename__ = "jupr_player"

    id: Mapped[int] = mapped_column(primary_key=True)
    dupr_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128), index=True)
    # Seed rating: either pulled from DUPR at creation time or set manually.
    seed_rating: Mapped[float] = mapped_column(Float, default=3.0)
    # Seed reliability (0-100). Lower = new players move faster.
    seed_reliability: Mapped[float] = mapped_column(Float, default=50.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class JuprGame(Base):
    """A JUPR-recorded doubles match. Teams are (p1,p2) vs (p3,p4)."""

    __tablename__ = "jupr_game"
    __table_args__ = (
        Index("ix_jupr_game_played_at", "played_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team1_p1_id: Mapped[int] = mapped_column(ForeignKey("jupr_player.id"), index=True)
    team1_p2_id: Mapped[int] = mapped_column(ForeignKey("jupr_player.id"), index=True)
    team2_p1_id: Mapped[int] = mapped_column(ForeignKey("jupr_player.id"), index=True)
    team2_p2_id: Mapped[int] = mapped_column(ForeignKey("jupr_player.id"), index=True)

    # Pre-match ratings captured at game time (so replay is deterministic and
    # resilient to players joining/leaving).
    pre_r1: Mapped[float] = mapped_column(Float)
    pre_r2: Mapped[float] = mapped_column(Float)
    pre_r3: Mapped[float] = mapped_column(Float)
    pre_r4: Mapped[float] = mapped_column(Float)

    games1: Mapped[int] = mapped_column(Integer)  # total games won by team 1
    games2: Mapped[int] = mapped_column(Integer)  # total games won by team 2
    winner: Mapped[int] = mapped_column(Integer)  # 1 or 2

    notes: Mapped[Optional[str]] = mapped_column(String(500))
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DuprCachedPlayer(Base):
    """
    A denormalized cache of a DUPR player for fast search + auto-fill in the
    forecast UI. Populated via:
      - POST /api/dupr/players/{id}/refresh (live fetch if creds configured)
      - scripts/seed_cached_players.py (bootstrap from existing dupr.sqlite)
    """

    __tablename__ = "dupr_cached_player"
    __table_args__ = (
        Index("ix_dupr_cached_name", "full_name"),
    )

    # Use DUPR's own id (stringified) as our primary key — stable and unique.
    dupr_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(128))
    first_name: Mapped[Optional[str]] = mapped_column(String(64))
    last_name: Mapped[Optional[str]] = mapped_column(String(64))
    short_dupr_id: Mapped[Optional[str]] = mapped_column(String(16), index=True)

    doubles: Mapped[Optional[float]] = mapped_column(Float)
    doubles_reliability: Mapped[Optional[float]] = mapped_column(Float)
    doubles_verified: Mapped[Optional[bool]] = mapped_column(default=False)

    singles: Mapped[Optional[float]] = mapped_column(Float)
    singles_reliability: Mapped[Optional[float]] = mapped_column(Float)
    singles_verified: Mapped[Optional[bool]] = mapped_column(default=False)

    image_url: Mapped[Optional[str]] = mapped_column(String(512))
    gender: Mapped[Optional[str]] = mapped_column(String(16))
    age: Mapped[Optional[int]] = mapped_column()

    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class FuprVote(Base):
    """A single community-submitted estimate of a player's "true" rating."""

    __tablename__ = "fupr_vote"
    __table_args__ = (
        # One vote per voter_key per player (idempotency + dedupe).
        UniqueConstraint("jupr_player_id", "voter_key", name="uq_fupr_vote_player_voter"),
        Index("ix_fupr_vote_player", "jupr_player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    jupr_player_id: Mapped[int] = mapped_column(ForeignKey("jupr_player.id"))
    rating: Mapped[float] = mapped_column(Float)  # 2.0 - 7.0
    confidence: Mapped[int] = mapped_column(Integer, default=3)  # 1 (low) - 5 (high)
    voter_key: Mapped[str] = mapped_column(String(128), index=True)  # IP hash or user id
    comment: Mapped[Optional[str]] = mapped_column(String(280))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
