import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.people import repository
from app.modules.people.models import Person


async def create_person(db: AsyncSession, user_id: uuid.UUID, name: str) -> Person:
    """Create new person"""
    existing_people = await repository.get_people(db, user_id)

    if any(person.name.lower() == name.lower() for person in existing_people):
        raise ValueError("Person with this name already exists")

    person = Person(
        user_id=user_id,
        name=name,
    )

    await repository.create_person(db, person)
    await db.commit()

    return person


async def get_people(db: AsyncSession, user_id: uuid.UUID) -> list[Person]:
    """Get all people of a user"""
    return await repository.get_people(db, user_id)


async def get_person(db: AsyncSession, person_id: uuid.UUID, user_id: uuid.UUID) -> Person:
    """Get person by person id and user id"""
    person = await repository.get_person_by_id(db, person_id, user_id)

    if not person:
        raise ValueError("Person not found")

    return person


async def update_person(db: AsyncSession, person_id: uuid.UUID, user_id: uuid.UUID, name: str | None = None) -> Person:
    """Update person name"""
    person = await repository.get_person_by_id(db, person_id, user_id)

    if not person:
        raise ValueError("Person not found")

    if name:
        person.name = name

    await repository.update_person(db, person)
    await db.commit()

    return person


async def delete_person(db: AsyncSession, person_id: uuid.UUID, user_id: uuid.UUID) -> None:
    person = await repository.get_person_by_id(db, person_id, user_id)

    if not person:
        raise ValueError("Person not found")

    await repository.soft_delete_person(db, person)
    await db.commit()