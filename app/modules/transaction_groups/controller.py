import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.financial_events.service import get_financial_event
from app.modules.transaction_groups.schemas import TransactionGroupResponse
from app.modules.transaction_groups.service import get_transaction_group, get_transaction_groups
from app.modules.users.models import User

router = APIRouter(prefix="/transaction-groups", tags=["Transaction Groups"])


@router.get("/{transaction_group_id}", response_model=TransactionGroupResponse)
async def get_transaction_group_controller(
    transaction_group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        transaction_group = await get_transaction_group(db, transaction_group_id)

        await get_financial_event(db, transaction_group.financial_event_id, current_user.id)

        return transaction_group

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get("/event/{financial_event_id}", response_model=list[TransactionGroupResponse])
async def get_transaction_groups_controller(
    financial_event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await get_financial_event(db, financial_event_id, current_user.id)

        return await get_transaction_groups(db, financial_event_id)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )