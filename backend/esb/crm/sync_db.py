"""Sync SQLAlchemy session for the CRM Verifier pipeline.

Ported from coach-devon's verifier/run.py, which uses sync SQLAlchemy
throughout (lazy relationship traversal, session.add/commit loops). Rather
than risk an error-prone rewrite of that interdependent ORM logic to async,
this module gives the verifier its own sync engine against the same
Postgres database. Router endpoints call into it via asyncio.to_thread().
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from esb.core.config import settings

_sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

_engine = create_engine(_sync_url, pool_pre_ping=True)
SyncSessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def sync_session() -> Session:
    return SyncSessionLocal()
