from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transaction_groups.models import TransactionGroup


async def create_transaction_group(db: AsyncSession, transaction_group: TransactionGroup) -> TransactionGroup:
    db.add(transaction_group)
    await db.flush()
    return transaction_group


async def get_transaction_group_by_id(db: AsyncSession, transaction_group_id) -> TransactionGroup | None:
    result = await db.execute(
        select(TransactionGroup).where(
            TransactionGroup.id == transaction_group_id,
        )
    )

    return result.scalar_one_or_none()


async def get_transaction_groups_by_event(db: AsyncSession, financial_event_id) -> list[TransactionGroup]:
    result = await db.execute(
        select(TransactionGroup)
        .where(TransactionGroup.financial_event_id == financial_event_id)
        .order_by(TransactionGroup.created_at.asc())
    )

    return list(result.scalars().all())


async def update_transaction_group(db: AsyncSession, transaction_group: TransactionGroup) -> TransactionGroup:
    await db.flush()
    return transaction_group