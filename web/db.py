"""
Database layer for the web app.

Uses SQLAlchemy with a DATABASE_URL env var:
- local dev: sqlite+pysqlite:///./duprly_web.db (default)
- production (Vercel + Neon Marketplace): postgresql+psycopg://...

Neon-provisioned env vars on Vercel are typically named POSTGRES_URL or
DATABASE_URL. We check both.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def _resolve_database_url() -> str:
    for key in ("DATABASE_URL", "POSTGRES_URL", "POSTGRES_PRISMA_URL"):
        val = os.environ.get(key)
        if val:
            # Neon often gives us postgres:// — SQLAlchemy needs postgresql+psycopg://
            if val.startswith("postgres://"):
                val = "postgresql+psycopg://" + val[len("postgres://"):]
            elif val.startswith("postgresql://"):
                val = "postgresql+psycopg://" + val[len("postgresql://"):]
            return val
    return "sqlite+pysqlite:///./duprly_web.db"


DATABASE_URL = _resolve_database_url()
_IS_SQLITE = DATABASE_URL.startswith("sqlite")

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        connect_args = {"check_same_thread": False} if _IS_SQLITE else {}
        _engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every cold start."""
    from web.models import Base

    engine = get_engine()
    Base.metadata.create_all(engine)
    _run_lightweight_migrations(engine)


def _run_lightweight_migrations(engine: Engine) -> None:
    """
    Idempotent column additions for pre-existing DBs.

    `Base.metadata.create_all()` only creates missing tables; it does not
    add columns to tables that already exist. We cache DUPR player data
    (DuprCachedPlayer) and evolve its schema as DUPR exposes more fields.
    A real Alembic migration is overkill for a cache that can be rebuilt
    from the live API in seconds, so we just do a safe ALTER TABLE when
    a known column is missing.

    Columns added here are listed as (table, column, ddl_type).
    """
    from sqlalchemy import inspect, text

    migrations: list[tuple[str, str, str]] = [
        ("dupr_cached_player", "short_address", "VARCHAR(128)"),
    ]

    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())

    with engine.begin() as conn:
        for table, column, ddl_type in migrations:
            if table not in existing_tables:
                continue
            cols = {c["name"] for c in insp.get_columns(table)}
            if column in cols:
                continue
            # ALTER TABLE ADD COLUMN is supported by both SQLite (>=3.35) and
            # Postgres. We keep it simple rather than branching per-dialect;
            # if we ever need DEFAULT values for existing rows, add them here.
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context-managed SQLAlchemy session."""
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    sess = _SessionLocal()
    try:
        yield sess
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as s:
        yield s
