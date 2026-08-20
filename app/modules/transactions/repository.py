from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transactions.models import Transaction


async def create_transaction(db: AsyncSession, transaction: Transaction) -> Transaction:
    db.add(transaction)
    await db.flush()
    return transaction


async def get_transaction_by_id(db: AsyncSession, transaction_id, user_id) -> Transaction | None:
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        )
    )

    return result.scalar_one_or_none()


async def get_transactions(db: AsyncSession, user_id) -> list[Transaction]:
    result = await db.execute(
        select(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        )
        .order_by(Transaction.transaction_date.desc())
    )

    return list(result.scalars().all())


async def update_transaction(db: AsyncSession, transaction: Transaction) -> Transaction:
    await db.flush()
    return transaction


async def soft_delete_transaction(db: AsyncSession, transaction: Transaction) -> None:
    transaction.deleted_at = datetime.now(timezone.utc)
    await db.flush()