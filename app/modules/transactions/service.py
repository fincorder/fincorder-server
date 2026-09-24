import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transactions import repository
from app.modules.transactions.models import (
    Transaction,
    TransactionDirection,
    TransactionType,
)
from app.modules.accounts import repository as accounts_repository
from app.modules.categories import repository as categories_repository
from app.modules.people import repository as people_repository
from app.modules.conversations.models import Conversation, ConversationStatus
from app.modules.financial_events.models import FinancialEvent, FinancialEventStatus
from app.modules.financial_events import repository as financial_events_repository
from app.modules.messages.models import Message, MessageRole
from app.modules.messages import repository as messages_repository
from app.modules.transaction_groups.service import create_transaction_group, mark_posted
from app.modules.conversations import repository as conversations_repository


async def create_transaction(
    db: AsyncSession,
    transaction_group_id: uuid.UUID,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    category_id: uuid.UUID | None,
    person_id: uuid.UUID | None,
    transaction_type: TransactionType,
    direction: TransactionDirection,
    amount,
    currency: str,
    description: str | None,
    transaction_date: datetime,
    commit: bool = True,
) -> Transaction:
    if not await repository.get_transaction_group_for_user(db, transaction_group_id, user_id):
        raise ValueError("Transaction group not found")

    if not await accounts_repository.get_account_by_id(db, account_id, user_id):
        raise ValueError("Account not found")

    if category_id and not await categories_repository.get_category_by_id(db, category_id, user_id):
        raise ValueError("Category not found")

    if person_id and not await people_repository.get_person_by_id(db, person_id, user_id):
        raise ValueError("Person not found")

    transaction = Transaction(
        transaction_group_id=transaction_group_id,
        user_id=user_id,
        account_id=account_id,
        category_id=category_id,
        person_id=person_id,
        type=transaction_type,
        direction=direction,
        amount=amount,
        currency=currency,
        description=description,
        transaction_date=transaction_date,
    )

    await repository.create_transaction(db, transaction)
    if commit:
        await db.commit()

    return transaction


async def create_manual_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    category_id: uuid.UUID | None,
    person_id: uuid.UUID | None,
    transaction_type: TransactionType,
    direction: TransactionDirection,
    amount,
    currency: str,
    description: str | None,
    transaction_date: datetime,
) -> Transaction:
    """Create a direct UI entry while preserving the event/group audit trail."""
    conversation = Conversation(
        user_id=user_id,
        title="Manual Transactions",
        status=ConversationStatus.ARCHIVED,
    )
    await conversations_repository.create_conversation(db, conversation)
    message = Message(
        conversation_id=conversation.id,
        role=MessageRole.SYSTEM,
        content="Manual transaction entry",
    )
    await messages_repository.create_message(db, message)
    event = FinancialEvent(
        conversation_id=conversation.id,
        source_message_id=message.id,
        status=FinancialEventStatus.COMPLETED,
        raw_text=description or "Manual transaction entry",
        extracted_data={"source": "manual"},
        missing_fields=[],
    )
    await financial_events_repository.create_financial_event(db, event)
    await db.flush()
    group = await create_transaction_group(db, event.id, commit=False)
    transaction = await create_transaction(
        db=db,
        transaction_group_id=group.id,
        user_id=user_id,
        account_id=account_id,
        category_id=category_id,
        person_id=person_id,
        transaction_type=transaction_type,
        direction=direction,
        amount=amount,
        currency=currency,
        description=description,
        transaction_date=transaction_date,
        commit=False,
    )
    await mark_posted(db, group, commit=False)
    await db.commit()
    return transaction


async def get_transactions(db: AsyncSession, user_id: uuid.UUID, **filters) -> list[Transaction]:
    return await repository.get_transactions(db, user_id, **filters)


async def get_transactions_page(db: AsyncSession, user_id: uuid.UUID, **filters) -> tuple[list[Transaction], int]:
    return await repository.get_transactions_page(db, user_id, **filters)


async def get_transaction(db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID) -> Transaction:
    transaction = await repository.get_transaction_by_id(db, transaction_id, user_id)
    if not transaction:
        raise ValueError("Transaction not found")

    return transaction


async def update_transaction(db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID, commit: bool = True, **updates) -> Transaction:
    transaction = await repository.get_transaction_by_id(db, transaction_id, user_id)
    if not transaction:
        raise ValueError("Transaction not found")

    if "account_id" in updates and updates["account_id"] is not None:
        if not await accounts_repository.get_account_by_id(db, updates["account_id"], user_id):
            raise ValueError("Account not found")

    if "category_id" in updates and updates["category_id"] is not None:
        if not await categories_repository.get_category_by_id(db, updates["category_id"], user_id):
            raise ValueError("Category not found")

    if "person_id" in updates and updates["person_id"] is not None:
        if not await people_repository.get_person_by_id(db, updates["person_id"], user_id):
            raise ValueError("Person not found")

    for field, value in updates.items():
        if field in {"account_id", "category_id", "person_id", "amount", "currency", "description", "transaction_date", "type", "direction"}:
            setattr(transaction, field, value)

    await repository.update_transaction(db, transaction)
    if commit:
        await db.commit()

    return transaction


async def delete_transaction(db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID, commit: bool = True) -> None:
    transaction = await repository.get_transaction_by_id(db, transaction_id, user_id)
    if not transaction:
        raise ValueError("Transaction not found")

    await repository.soft_delete_transaction(db, transaction)
    if commit:
        await db.commit()
