import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.financial_events import repository as financial_events_repository
from app.modules.transaction_groups import repository
from app.modules.transaction_groups.models import TransactionGroup, TransactionGroupStatus


async def create_transaction_group(db: AsyncSession, financial_event_id: uuid.UUID, commit: bool = True) -> TransactionGroup:
    event = await financial_events_repository.get_financial_event_by_id(db, financial_event_id)
    if not event:
        raise ValueError("Financial event not found")

    transaction_group = TransactionGroup(financial_event_id=financial_event_id)

    await repository.create_transaction_group(db, transaction_group)
    if commit:
        await db.commit()

    return transaction_group


async def get_transaction_group(db: AsyncSession, transaction_group_id: uuid.UUID) -> TransactionGroup:
    transaction_group = await repository.get_transaction_group_by_id(db, transaction_group_id)
    if not transaction_group:
        raise ValueError("Transaction group not found")

    return transaction_group


async def get_transaction_groups(db: AsyncSession, financial_event_id: uuid.UUID) -> list[TransactionGroup]:
    return await repository.get_transaction_groups_by_event(db, financial_event_id)


async def mark_posted(db: AsyncSession, transaction_group: TransactionGroup, commit: bool = True) -> TransactionGroup:
    transaction_group.status = TransactionGroupStatus.POSTED
    await repository.update_transaction_group(db, transaction_group)
    if commit:
        await db.commit()
    return transaction_group


async def mark_reversed(db: AsyncSession, transaction_group: TransactionGroup, commit: bool = True) -> TransactionGroup:
    transaction_group.status = TransactionGroupStatus.REVERSED
    await repository.update_transaction_group(db, transaction_group)
    if commit:
        await db.commit()
    return transaction_group
