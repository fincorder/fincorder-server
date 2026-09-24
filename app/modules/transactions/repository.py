from datetime import datetime, timezone

from sqlalchemy import func, select
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


def _transaction_query(
    user_id,
    transaction_type=None,
    direction=None,
    account_id=None,
    category_id=None,
    person_id=None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
):
    query = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.deleted_at.is_(None),
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
    return query


def _sorted_query(query, sort_by: str = "transaction_date", sort_order: str = "desc"):
    columns = {
        "transaction_date": Transaction.transaction_date,
        "amount": Transaction.amount,
        "created_at": Transaction.created_at,
    }
    column = columns.get(sort_by, Transaction.transaction_date)
    ordering = column.asc() if sort_order == "asc" else column.desc()
    return query.order_by(ordering, Transaction.created_at.desc())


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
    sort_by: str = "transaction_date",
    sort_order: str = "desc",
) -> list[Transaction]:
    query = (
        _sorted_query(_transaction_query(
            user_id=user_id,
            transaction_type=transaction_type,
            direction=direction,
            account_id=account_id,
            category_id=category_id,
            person_id=person_id,
            date_from=date_from,
            date_to=date_to,
            search=search,
        ), sort_by, sort_order)
        .options(
            joinedload(Transaction.account),
            joinedload(Transaction.category),
            joinedload(Transaction.person),
        )
    )

    result = await db.execute(
        query
        .offset(offset)
        .limit(limit)
    )

    return list(result.scalars().all())


async def get_transactions_page(db: AsyncSession, user_id, **filters) -> tuple[list[Transaction], int]:
    query = _transaction_query(
        user_id=user_id,
        transaction_type=filters.get("transaction_type"),
        direction=filters.get("direction"),
        account_id=filters.get("account_id"),
        category_id=filters.get("category_id"),
        person_id=filters.get("person_id"),
        date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
        search=filters.get("search"),
    )
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        _sorted_query(query, filters.get("sort_by", "transaction_date"), filters.get("sort_order", "desc"))
        .options(
            joinedload(Transaction.account),
            joinedload(Transaction.category),
            joinedload(Transaction.person),
        )
        .offset(filters.get("offset", 0))
        .limit(filters.get("limit", 50))
    )
    return list(result.scalars().all()), int(total or 0)


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
