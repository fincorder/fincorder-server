import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.transactions.models import TransactionDirection, TransactionType
from app.modules.transactions.schemas import CreateManualTransactionRequest, CreateTransactionRequest, TransactionPageResponse, TransactionResponse, UpdateTransactionRequest
from app.modules.transactions.service import create_manual_transaction, create_transaction, delete_transaction, get_transaction, get_transactions, get_transactions_page, update_transaction
from app.modules.users.models import User

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/manual", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_manual_transaction_controller(
    data: CreateManualTransactionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await create_manual_transaction(
            db=db,
            user_id=current_user.id,
            account_id=data.account_id,
            category_id=data.category_id,
            person_id=data.person_id,
            transaction_type=TransactionType(data.type),
            direction=TransactionDirection(data.direction),
            amount=data.amount,
            currency=data.currency.upper(),
            description=data.description,
            transaction_date=data.transaction_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction_controller(
    data: CreateTransactionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await create_transaction(
            db=db,
            transaction_group_id=data.transaction_group_id,
            user_id=current_user.id,
            account_id=data.account_id,
            category_id=data.category_id,
            person_id=data.person_id,
            transaction_type=TransactionType(data.type),
            direction=TransactionDirection(data.direction),
            amount=data.amount,
            currency=data.currency.upper(),
            description=data.description,
            transaction_date=data.transaction_date,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get("", response_model=list[TransactionResponse])
async def get_transactions_controller(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    type: TransactionType | None = Query(default=None),
    direction: TransactionDirection | None = Query(default=None),
    account_id: uuid.UUID | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
    person_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must be before or equal to date_to",
        )

    return await get_transactions(
        db,
        current_user.id,
        limit=limit,
        offset=offset,
        transaction_type=type,
        direction=direction,
        account_id=account_id,
        category_id=category_id,
        person_id=person_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )


@router.get("/page", response_model=TransactionPageResponse)
async def get_transactions_page_controller(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    type: TransactionType | None = Query(default=None),
    direction: TransactionDirection | None = Query(default=None),
    account_id: uuid.UUID | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
    person_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    sort_by: Literal["transaction_date", "amount", "created_at"] = Query(default="transaction_date"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="date_from must be before or equal to date_to")

    items, total = await get_transactions_page(
        db,
        current_user.id,
        limit=limit,
        offset=offset,
        transaction_type=type,
        direction=direction,
        account_id=account_id,
        category_id=category_id,
        person_id=person_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset, "has_next": offset + len(items) < total}


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction_controller(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await get_transaction(db, transaction_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction_controller(
    transaction_id: uuid.UUID,
    data: UpdateTransactionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        updates = data.model_dump(exclude_unset=True)
        if "type" in updates and updates["type"] is not None:
            updates["type"] = TransactionType(updates["type"])
        if "direction" in updates and updates["direction"] is not None:
            updates["direction"] = TransactionDirection(updates["direction"])
        if "currency" in updates and updates["currency"] is not None:
            updates["currency"] = updates["currency"].upper()

        return await update_transaction(
            db=db,
            transaction_id=transaction_id,
            user_id=current_user.id,
            **updates,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction_controller(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await delete_transaction(db, transaction_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
