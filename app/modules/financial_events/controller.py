import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.financial_events.schemas import FinancialEventResponse
from app.modules.financial_events.service import get_financial_event, get_financial_events
from app.modules.users.models import User

router = APIRouter(prefix="/financial-events", tags=["Financial Events"])


@router.get("/{event_id}", response_model=FinancialEventResponse)
async def get_financial_event_controller(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await get_financial_event(
            db=db,
            event_id=event_id,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get("/conversation/{conversation_id}", response_model=list[FinancialEventResponse])
async def get_financial_events_controller(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await get_financial_events(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )