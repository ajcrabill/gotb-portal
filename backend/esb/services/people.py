"""People service — Person entity management."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.models.user import Person


async def get_by_email(db: AsyncSession, email: str) -> Person | None:
    return await db.scalar(select(Person).where(Person.email == email.lower().strip()))


async def get_by_id(db: AsyncSession, person_id: UUID) -> Person | None:
    return await db.scalar(select(Person).where(Person.id == person_id))


async def get_or_create(db: AsyncSession, email: str, name: str = "") -> tuple[Person, bool]:
    """Return (person, created). Name only used on creation."""
    email = email.lower().strip()
    person = await get_by_email(db, email)
    if person:
        return person, False
    person = Person(email=email, name=name or email.split("@")[0])
    db.add(person)
    await db.flush()
    return person, True
