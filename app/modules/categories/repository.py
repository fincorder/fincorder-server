from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.categories.models import Category, CategoryType


async def create_category(db: AsyncSession, category: Category) -> Category:
    """Create new expense category"""
    db.add(category)
    await db.flush()
    return category


async def get_category_by_id(db: AsyncSession, category_id, user_id) -> Category | None:
    """Fetch category by category id and user id"""
    result = await db.execute(
        select(Category).where(
            Category.id == category_id,
            Category.user_id == user_id,
            Category.deleted_at.is_(None),
        )
    )

    return result.scalar_one_or_none()


async def get_categories(db: AsyncSession, user_id) -> list[Category]:
    """Fetch all categories of a user"""
    result = await db.execute(
        select(Category).where(
            Category.user_id == user_id,
            Category.deleted_at.is_(None),
        )
        .order_by(Category.created_at)
    )

    return list(result.scalars().all())


async def update_category(db: AsyncSession, category: Category) -> Category:
    """Update category data"""
    await db.flush()
    return category


async def soft_delete_category(db: AsyncSession, category: Category) -> None:
    """Soft delete category"""
    category.deleted_at = datetime.now(timezone.utc)
    await db.flush()


async def create_default_categories(db: AsyncSession, user_id):
    db.add_all([
        Category(user_id=user_id, name="Food", type=CategoryType.EXPENSE),
        Category(user_id=user_id, name="Transport", type=CategoryType.EXPENSE),
        Category(user_id=user_id, name="Shopping", type=CategoryType.EXPENSE),
        Category(user_id=user_id, name="Bills", type=CategoryType.EXPENSE),
        Category(user_id=user_id, name="Entertainment", type=CategoryType.EXPENSE),
        Category(user_id=user_id, name="Health", type=CategoryType.EXPENSE),
        Category(user_id=user_id, name="Other", type=CategoryType.EXPENSE),
        Category(user_id=user_id, name="Salary", type=CategoryType.INCOME),
        Category(user_id=user_id, name="Freelance", type=CategoryType.INCOME),
        Category(user_id=user_id, name="Gift", type=CategoryType.INCOME),
        Category(user_id=user_id, name="Refund", type=CategoryType.INCOME),
        Category(user_id=user_id, name="Other", type=CategoryType.INCOME),
    ])