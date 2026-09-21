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


async def get_transactions(db: AsyncSession, user_id: uuid.UUID, **filters) -> list[Transaction]:
    return await repository.get_transactions(db, user_id, **filters)


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
