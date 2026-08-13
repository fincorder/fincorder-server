from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts.models import Account


async def create_account(db: AsyncSession, account: Account) -> Account:
    """Create new money account"""
    db.add(account)
    await db.flush()
    return account


async def get_account_by_id(db: AsyncSession, account_id, user_id) -> Account | None:
    """Fetch account by account id and user id"""
    result = await db.execute(
        select(Account).where(
            Account.id == account_id,
            Account.user_id == user_id,
            Account.deleted_at.is_(None),
        )
    )

    return result.scalar_one_or_none()


async def get_accounts(db: AsyncSession, user_id) -> list[Account]:
    """Fetch all accounts of a user"""
    result = await db.execute(
        select(Account).where(
            Account.user_id == user_id,
            Account.deleted_at.is_(None),
        )
        .order_by(Account.created_at)
    )

    return list(result.scalars().all())


async def update_account(db: AsyncSession, account: Account) -> Account:
    """Update account data"""
    await db.flush()
    return account


async def soft_delete_account(db: AsyncSession, account: Account) -> None:
    """Soft delete account"""
    account.deleted_at = datetime.now(timezone.utc)
    account.is_active = False
    await db.flush()


async def create_default_accounts(db: AsyncSession, user_id):
    db.add_all([
        Account(user_id=user_id, name="Salary Account"),
        Account(user_id=user_id, name="Spending Account"),
        Account(user_id=user_id, name="Cash"),
    ])