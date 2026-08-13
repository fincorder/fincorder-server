import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.accounts.schemas import AccountResponse, CreateAccountRequest, UpdateAccountRequest
from app.modules.accounts.service import create_account, delete_account, get_account, get_accounts, update_account
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User


router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account_controller(
    data: CreateAccountRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        account = await create_account(
            db=db,
            user_id=current_user.id,
            name=data.name,
            currency=data.currency.upper(),
        )
        return account
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.get("", response_model=list[AccountResponse])
async def get_accounts_controller(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_accounts(db, current_user.id)


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account_controller(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await get_account(db, account_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account_controller(
    account_id: uuid.UUID,
    data: UpdateAccountRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await update_account(
            db=db,
            account_id=account_id,
            user_id=current_user.id,
            name=data.name,
            currency=data.currency.upper() if data.currency else None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account_controller(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await delete_account(db, account_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )