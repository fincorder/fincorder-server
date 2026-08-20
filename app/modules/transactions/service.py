import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transactions import repository
from app.modules.transactions.models import (
    Transaction,
    TransactionDirection,
    TransactionType,
)


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
) -> Transaction:
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
    await db.commit()

    return transaction


async def get_transactions(db: AsyncSession, user_id: uuid.UUID) -> list[Transaction]:
    return await repository.get_transactions(db, user_id)


async def get_transaction(db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID) -> Transaction:
    transaction = await repository.get_transaction_by_id(db, transaction_id, user_id)
    if not transaction:
        raise ValueError("Transaction not found")

    return transaction


async def update_transaction(db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID, **updates) -> Transaction:
    transaction = await repository.get_transaction_by_id(db, transaction_id, user_id)
    if not transaction:
        raise ValueError("Transaction not found")

    for field, value in updates.items():
        if value is not None:
            setattr(transaction, field, value)

    await repository.update_transaction(db, transaction)
    await db.commit()

    return transaction


async def delete_transaction(db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID) -> None:
    transaction = await repository.get_transaction_by_id(db, transaction_id, user_id)
    if not transaction:
        raise ValueError("Transaction not found")

    await repository.soft_delete_transaction(db, transaction)
    await db.commit()