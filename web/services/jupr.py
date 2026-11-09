"""
JUPR service — our local DUPR mirror.

- Each JuprPlayer has a seed rating (e.g. from DUPR or set to 3.0).
- A JuprGame stores (team1, team2, games1, games2) plus the *pre-match* ratings
  used to compute its impact. We snapshot the pre-match ratings at game-creation
  time so that the ledger is append-only and replay is deterministic.
- Current JUPR rating for any player = seed + sum(delta_for_player across all
  JUPR games they played in, in chronological order).

Rationale for snapshotting: it mirrors how DUPR produces a deterministic
rating history, and it means we don't need to recompute the world when a new
game is added.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from web.models import JuprGame, JuprPlayer
from web.services.forecast import get_predictor


@dataclass
class JuprRating:
    player_id: int
    full_name: str
    seed_rating: float
    current_rating: float
    games_played: int
    last_delta: Optional[float]


def _current_rating(session: Session, player: JuprPlayer) -> JuprRating:
    """Replay all JUPR games for this player to produce their current rating."""
    predictor = get_predictor()
    games = (
        session.execute(
            select(JuprGame)
            .where(
                or_(
                    JuprGame.team1_p1_id == player.id,
                    JuprGame.team1_p2_id == player.id,
                    JuprGame.team2_p1_id == player.id,
                    JuprGame.team2_p2_id == player.id,
                )
            )
            .order_by(JuprGame.played_at.asc(), JuprGame.id.asc())
        )
        .scalars()
        .all()
    )
    rating = player.seed_rating
    last_delta: Optional[float] = None
    for g in games:
        d1, d2, d3, d4 = predictor.predict_impacts(
            g.pre_r1, g.pre_r2, g.pre_r3, g.pre_r4,
            g.games1, g.games2, g.winner,
        )
        if g.team1_p1_id == player.id:
            delta = d1
        elif g.team1_p2_id == player.id:
            delta = d2
        elif g.team2_p1_id == player.id:
            delta = d3
        else:
            delta = d4
        rating += delta
        last_delta = delta
    return JuprRating(
        player_id=player.id,
        full_name=player.full_name,
        seed_rating=player.seed_rating,
        current_rating=rating,
        games_played=len(games),
        last_delta=last_delta,
    )


def get_rating(session: Session, player_id: int) -> Optional[JuprRating]:
    p = session.get(JuprPlayer, player_id)
    if p is None:
        return None
    return _current_rating(session, p)


def create_player(
    session: Session,
    full_name: str,
    seed_rating: float = 3.0,
    seed_reliability: float = 50.0,
    dupr_id: Optional[str] = None,
) -> JuprPlayer:
    p = JuprPlayer(
        full_name=full_name,
        seed_rating=seed_rating,
        seed_reliability=seed_reliability,
        dupr_id=dupr_id,
    )
    session.add(p)
    session.flush()
    return p


def find_or_create_by_dupr_id(
    session: Session,
    *,
    dupr_id: str,
    full_name: str,
    seed_rating: float = 3.0,
    seed_reliability: float = 50.0,
) -> JuprPlayer:
    """
    Look up a JuprPlayer by DUPR id, or create one seeded with the DUPR
    rating/reliability. Used by the forecast card's "Log to JUPR" button
    so a user can record a real match they just played (with four DUPR-
    searched players) without manually creating each player first.

    Mutation policy: we intentionally do NOT overwrite an existing
    player's seed rating — that row is the canonical source of truth
    for their JUPR history. If the name ever drifts, that's OK too;
    the DUPR id is the stable link.
    """
    dupr_id = str(dupr_id).strip()
    if not dupr_id:
        raise ValueError("dupr_id is required")
    existing = session.execute(
        select(JuprPlayer).where(JuprPlayer.dupr_id == dupr_id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    p = JuprPlayer(
        full_name=full_name,
        seed_rating=seed_rating,
        seed_reliability=seed_reliability,
        dupr_id=dupr_id,
    )
    session.add(p)
    session.flush()
    return p


def record_game(
    session: Session,
    team1: List[int],
    team2: List[int],
    games1: int,
    games2: int,
    notes: Optional[str] = None,
) -> JuprGame:
    """
    Record a new JUPR game. Pre-match ratings are snapshotted using each
    player's *current* JUPR rating at time of insert.
    """
    if len(team1) != 2 or len(team2) != 2:
        raise ValueError("Each team must have exactly 2 players (doubles).")
    if games1 == games2:
        raise ValueError("Games cannot tie — one team must win.")
    ids = team1 + team2
    if len(set(ids)) != 4:
        raise ValueError("All 4 players must be distinct.")

    players = session.execute(
        select(JuprPlayer).where(JuprPlayer.id.in_(ids))
    ).scalars().all()
    players_by_id = {p.id: p for p in players}
    missing = [pid for pid in ids if pid not in players_by_id]
    if missing:
        raise ValueError(f"Unknown player ids: {missing}")

    # Snapshot pre-match ratings via current JUPR rating for each player.
    def _r(pid: int) -> float:
        return _current_rating(session, players_by_id[pid]).current_rating

    pre_r1 = _r(team1[0])
    pre_r2 = _r(team1[1])
    pre_r3 = _r(team2[0])
    pre_r4 = _r(team2[1])

    winner = 1 if games1 > games2 else 2
    game = JuprGame(
        team1_p1_id=team1[0],
        team1_p2_id=team1[1],
        team2_p1_id=team2[0],
        team2_p2_id=team2[1],
        pre_r1=pre_r1, pre_r2=pre_r2, pre_r3=pre_r3, pre_r4=pre_r4,
        games1=games1, games2=games2, winner=winner,
        notes=notes,
    )
    session.add(game)
    session.flush()
    return game


def leaderboard(session: Session, limit: int = 50) -> List[JuprRating]:
    players = session.execute(select(JuprPlayer)).scalars().all()
    ratings = [_current_rating(session, p) for p in players]
    ratings.sort(key=lambda r: r.current_rating, reverse=True)
    return ratings[:limit]


def recent_games(session: Session, player_id: Optional[int] = None, limit: int = 50) -> List[JuprGame]:
    stmt = select(JuprGame).order_by(JuprGame.played_at.desc(), JuprGame.id.desc()).limit(limit)
    if player_id is not None:
        stmt = select(JuprGame).where(
            or_(
                JuprGame.team1_p1_id == player_id,
                JuprGame.team1_p2_id == player_id,
                JuprGame.team2_p1_id == player_id,
                JuprGame.team2_p2_id == player_id,
            )
        ).order_by(JuprGame.played_at.desc(), JuprGame.id.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())
