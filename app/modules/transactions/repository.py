from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transactions.models import Transaction
from app.modules.transaction_groups.models import TransactionGroup
from app.modules.financial_events.models import FinancialEvent
from app.modules.conversations.models import Conversation


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


async def get_transactions(
    db: AsyncSession,
    user_id,
    limit: int = 50,
    offset: int = 0,
    transaction_type=None,
    direction=None,
    account_id=None,
    category_id=None,
    person_id=None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
) -> list[Transaction]:
    query = (
        select(Transaction)
        .options(
            joinedload(Transaction.account),
            joinedload(Transaction.category),
            joinedload(Transaction.person),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        )
    )

    if transaction_type:
        query = query.where(Transaction.type == transaction_type)
    if direction:
        query = query.where(Transaction.direction == direction)
    if account_id:
        query = query.where(Transaction.account_id == account_id)
    if category_id:
        query = query.where(Transaction.category_id == category_id)
    if person_id:
        query = query.where(Transaction.person_id == person_id)
    if date_from:
        query = query.where(Transaction.transaction_date >= date_from)
    if date_to:
        query = query.where(Transaction.transaction_date <= date_to)
    if search:
        query = query.where(Transaction.description.ilike(f"%{search}%"))

    result = await db.execute(
        query
        .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    return list(result.scalars().all())


async def get_transaction_group_for_user(db: AsyncSession, transaction_group_id, user_id):
    result = await db.execute(
        select(TransactionGroup)
        .join(FinancialEvent, TransactionGroup.financial_event_id == FinancialEvent.id)
        .join(Conversation, FinancialEvent.conversation_id == Conversation.id)
        .where(
            TransactionGroup.id == transaction_group_id,
            Conversation.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def update_transaction(db: AsyncSession, transaction: Transaction) -> Transaction:
    await db.flush()
    return transaction


async def soft_delete_transaction(db: AsyncSession, transaction: Transaction) -> None:
    transaction.deleted_at = datetime.now(timezone.utc)
    await db.flush()
