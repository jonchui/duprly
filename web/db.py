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
