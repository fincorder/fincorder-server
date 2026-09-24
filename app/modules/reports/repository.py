from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts.models import Account
from app.modules.categories.models import Category
from app.modules.people.models import Person
from app.modules.transaction_groups.models import TransactionGroup, TransactionGroupStatus
from app.modules.transactions.models import Transaction
from app.modules.reports.filters import ReportFilters, date_bounds
from app.modules.conversations.models import Conversation
from app.modules.financial_events.models import FinancialEvent, FinancialEventStatus


@dataclass(frozen=True)
class Fact:
    id: UUID
    group_id: UUID
    type: str
    direction: str
    amount: Decimal
    currency: str
    description: str | None
    transaction_date: datetime
    account_id: UUID
    account: str
    account_deleted: bool
    category_id: UUID | None
    category: str | None
    person_id: UUID | None
    person: str | None


async def load_facts(db: AsyncSession, user_id: UUID, filters: ReportFilters, timezone_name: str | None, *, settlement: bool = False, transfers: bool = False) -> list[Fact]:
    start, end = date_bounds(filters, timezone_name)
    query = (
        select(Transaction, Account.name, Account.deleted_at, Category.name, Person.name)
        .join(TransactionGroup, Transaction.transaction_group_id == TransactionGroup.id)
        .join(Account, Account.id == Transaction.account_id)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .outerjoin(Person, Person.id == Transaction.person_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
            TransactionGroup.status == TransactionGroupStatus.POSTED,
            Transaction.currency == filters.currency,
        )
    )
    if not settlement and start:
        query = query.where(Transaction.transaction_date >= start)
    if end:
        query = query.where(Transaction.transaction_date < end)
    if settlement:
        query = query.where(Transaction.type.in_(["LEND", "BORROW", "REPAYMENT"]))
    elif transfers:
        query = query.where(Transaction.type == "TRANSFER")
    else:
        if filters.account_id:
            query = query.where(Transaction.account_id == filters.account_id)
        if filters.category_id:
            query = query.where(Transaction.category_id == filters.category_id)
        if filters.person_id:
            query = query.where(Transaction.person_id == filters.person_id)
        if filters.transaction_type:
            query = query.where(Transaction.type == filters.transaction_type.upper())
        if filters.direction:
            query = query.where(Transaction.direction == filters.direction.upper())
        if filters.search:
            pattern = f"%{filters.search.strip()}%"
            query = query.where(or_(Transaction.description.ilike(pattern), Account.name.ilike(pattern), Category.name.ilike(pattern), Person.name.ilike(pattern)))
    if settlement and filters.person_id:
        query = query.where(Transaction.person_id == filters.person_id)
    result = await db.execute(query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc()))
    return [
        Fact(
            id=transaction.id,
            group_id=transaction.transaction_group_id,
            type=transaction.type.value,
            direction=transaction.direction.value,
            amount=transaction.amount,
            currency=transaction.currency,
            description=transaction.description,
            transaction_date=transaction.transaction_date,
            account_id=transaction.account_id,
            account=account_name,
            account_deleted=account_deleted_at is not None,
            category_id=transaction.category_id,
            category=category_name,
            person_id=transaction.person_id,
            person=person_name,
        )
        for transaction, account_name, account_deleted_at, category_name, person_name in result.all()
    ]


async def capture_quality_counts(db: AsyncSession, user_id: UUID, filters: ReportFilters, timezone_name: str | None) -> dict[str, int]:
    start, end = date_bounds(filters, timezone_name)
    query = (
        select(FinancialEvent.status, func.count(FinancialEvent.id))
        .join(Conversation, Conversation.id == FinancialEvent.conversation_id)
        .where(Conversation.user_id == user_id)
    )
    if start:
        query = query.where(FinancialEvent.created_at >= start)
    if end:
        query = query.where(FinancialEvent.created_at < end)
    result = await db.execute(query.group_by(FinancialEvent.status))
    counts = {status.value: count for status, count in result.all()}
    return {
        "pending_review": counts.get(FinancialEventStatus.AWAITING_CONFIRMATION.value, 0),
        "needs_clarification": counts.get(FinancialEventStatus.NEEDS_CLARIFICATION.value, 0),
        "failed_captures": counts.get(FinancialEventStatus.FAILED.value, 0),
        "rejected_proposals": counts.get(FinancialEventStatus.REJECTED.value, 0),
    }


async def report_options(db: AsyncSession, user_id: UUID) -> dict:
    accounts = (await db.execute(select(Account.id, Account.name, Account.currency).where(Account.user_id == user_id).order_by(Account.name))).all()
    categories = (await db.execute(select(Category.id, Category.name).where(Category.user_id == user_id).order_by(Category.name))).all()
    people = (await db.execute(select(Person.id, Person.name).where(Person.user_id == user_id).order_by(Person.name))).all()
    currencies = (await db.execute(select(Transaction.currency).where(Transaction.user_id == user_id).distinct())).scalars().all()
    return {
        "accounts": [{"id": str(id), "name": name, "currency": currency} for id, name, currency in accounts],
        "categories": [{"id": str(id), "name": name} for id, name in categories],
        "people": [{"id": str(id), "name": name} for id, name in people],
        "currencies": sorted(set(currencies) | {currency for _, _, currency in accounts} | {"INR"}),
    }
