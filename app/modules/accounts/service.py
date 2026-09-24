import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts import repository
from app.modules.accounts.models import Account


async def create_account(db: AsyncSession, user_id: uuid.UUID, name: str, currency: str = "INR", is_default: bool = False) -> Account:
    """Create new account"""
    existing_accounts = await repository.get_accounts(db, user_id)

    if any(acc.name.lower() == name.lower() for acc in existing_accounts):
        raise ValueError("Account with this name already exists")

    if is_default:
        for account in existing_accounts:
            account.is_default = False

    account = Account(
        user_id=user_id,
        name=name,
        currency=currency,
        is_default=is_default,
    )

    await repository.create_account(db, account)
    await db.commit()

    return account


async def get_accounts(db: AsyncSession, user_id: uuid.UUID) -> list[Account]:
    """Get all accounts of a user"""
    return await repository.get_accounts(db, user_id)


async def get_account(db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID) -> Account:
    """Get account by account id and user id"""
    account = await repository.get_account_by_id(db, account_id, user_id)

    if not account:
        raise ValueError("Account not found")

    return account


async def update_account(db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID, name: str | None = None, currency: str | None = None, is_default: bool | None = None) -> Account:
    """Update user account name or currency"""
    account = await repository.get_account_by_id(db, account_id, user_id)

    if not account:
        raise ValueError("Account not found")

    if name:
        account.name = name

    if currency:
        account.currency = currency

    if is_default:
        for existing_account in await repository.get_accounts(db, user_id):
            existing_account.is_default = existing_account.id == account.id
    elif is_default is False:
        account.is_default = False

    await repository.update_account(db, account)
    await db.commit()

    return account


async def delete_account(db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID) -> None:
    account = await repository.get_account_by_id(db, account_id, user_id)

    if not account:
        raise ValueError("Account not found")

    await repository.soft_delete_account(db, account)
    await db.commit()
