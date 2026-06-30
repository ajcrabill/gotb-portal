"""Test fixtures for esb-portal backend.

Uses an in-memory SQLite database (via aiosqlite) so tests never require
a running PostgreSQL instance. Postgres-specific SQL (JSONB, triggers) is
not present in the SQLAlchemy layer, so SQLite works for unit/integration
tests of service logic.

For CI integration tests against a real Postgres, the test runner uses
the `DATABASE_URL` env var pointing at a Postgres test database.
"""
import os
import pytest
from uuid import uuid4
from datetime import datetime, timezone

# Force a valid env before any ESB imports so Settings doesn't raise
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-!")
os.environ.setdefault("ENVIRONMENT", "test")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from esb.models.base import Base
from esb.models import user, scoring, audit, district, billing, assessment, irr  # register all models


@pytest.fixture(scope="session")
def engine():
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture(scope="session")
async def tables(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db(engine, tables) -> AsyncSession:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_person(db):
    from esb.models.user import Person
    person = Person(
        id=uuid4(),
        email=f"test-{uuid4().hex[:8]}@example.com",
        name="Test Person",
    )
    db.add(person)
    await db.flush()
    return person


@pytest.fixture
async def facilitator_person(db):
    from esb.models.user import Person, RoleMembership, RoleType
    person = Person(
        id=uuid4(),
        email=f"facilitator-{uuid4().hex[:8]}@example.com",
        name="Test Facilitator",
    )
    db.add(person)
    await db.flush()

    role = RoleMembership(
        person_id=person.id,
        role=RoleType.certified_facilitator,
        effective_from=datetime.now(timezone.utc),
    )
    db.add(role)
    await db.flush()
    return person
