from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.people.models import Person


async def create_person(db: AsyncSession, person: Person) -> Person:
    """Create new person"""
    db.add(person)
    await db.flush()
    return person


async def get_person_by_id(db: AsyncSession, person_id, user_id) -> Person | None:
    """Fetch person by person id and user id"""
    result = await db.execute(
        select(Person).where(
            Person.id == person_id,
            Person.user_id == user_id,
            Person.deleted_at.is_(None),
        )
    )

    return result.scalar_one_or_none()


async def get_people(db: AsyncSession, user_id) -> list[Person]:
    """Fetch all people of a user"""
    result = await db.execute(
        select(Person).where(
            Person.user_id == user_id,
            Person.deleted_at.is_(None),
        )
        .order_by(Person.created_at)
    )

    return list(result.scalars().all())


async def update_person(db: AsyncSession, person: Person) -> Person:
    """Update person data"""
    await db.flush()
    return person


async def soft_delete_person(db: AsyncSession, person: Person) -> None:
    """Soft delete person"""
    person.deleted_at = datetime.now(timezone.utc)
    await db.flush()