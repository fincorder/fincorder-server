import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.financial_events.schemas import FinancialEventResponse, FinancialEventReviewPageResponse
from app.modules.financial_events.service import get_financial_event, get_financial_events, get_review_events_page
from app.modules.users.models import User

router = APIRouter(prefix="/financial-events", tags=["Financial Events"])


@router.get("/review", response_model=FinancialEventReviewPageResponse)
async def get_review_events_page_controller(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await get_review_events_page(
            db=db,
            user=current_user,
            limit=limit,
            offset=offset,
            search=search,
            month=month,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


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
