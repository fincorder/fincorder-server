import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.categories import repository
from app.modules.categories.models import Category, CategoryType


async def create_category(db: AsyncSession, user_id: uuid.UUID, name: str, type: str = "expense") -> Category:
    """Create new category"""
    existing_categories = await repository.get_categories(db, user_id)

    if any(cat.name.lower() == name.lower() and cat.type == type for cat in existing_categories):
        raise ValueError("Category with this name already exists")

    category = Category(
        user_id=user_id,
        name=name,
        type=type,
    )

    await repository.create_category(db, category)
    await db.commit()

    return category


async def get_categories(db: AsyncSession, user_id: uuid.UUID) -> list[Category]:
    """Get all categories of a user"""
    return await repository.get_categories(db, user_id)


async def get_category(db: AsyncSession, category_id: uuid.UUID, user_id: uuid.UUID) -> Category:
    """Get category by category id and user id"""
    category = await repository.get_category_by_id(db, category_id, user_id)

    if not category:
        raise ValueError("Category not found")

    return category


async def update_category(db: AsyncSession, category_id: uuid.UUID, user_id: uuid.UUID, name: str | None = None) -> Category:
    """Update user category name or type"""
    category = await repository.get_category_by_id(db, category_id, user_id)

    if not category:
        raise ValueError("Category not found")

    if name:
        category.name = name

    await repository.update_category(db, category)
    await db.commit()

    return category


async def delete_category(db: AsyncSession, category_id: uuid.UUID, user_id: uuid.UUID) -> None:
    category = await repository.get_category_by_id(db, category_id, user_id)

    if not category:
        raise ValueError("Category not found")

    await repository.soft_delete_category(db, category)
    await db.commit()