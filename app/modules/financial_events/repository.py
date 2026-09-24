from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.conversations.models import Conversation
from app.modules.financial_events.models import FinancialEvent, FinancialEventStatus


async def create_financial_event(db: AsyncSession, event: FinancialEvent) -> FinancialEvent:
    db.add(event)
    await db.flush()
    return event


async def get_financial_event_by_id(db: AsyncSession, event_id) -> FinancialEvent | None:
    result = await db.execute(
        select(FinancialEvent).where(
            FinancialEvent.id == event_id,
        )
    )

    return result.scalar_one_or_none()


async def get_financial_events_by_conversation(db: AsyncSession, conversation_id) -> list[FinancialEvent]:
    result = await db.execute(
        select(FinancialEvent)
        .where(FinancialEvent.conversation_id == conversation_id)
        .order_by(FinancialEvent.created_at.asc())
    )

    return list(result.scalars().all())


async def get_review_events_page(
    db: AsyncSession,
    user_id,
    *,
    limit: int = 25,
    offset: int = 0,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[tuple[FinancialEvent, str | None]], int]:
    query = (
        select(FinancialEvent, Conversation.title)
        .join(Conversation, Conversation.id == FinancialEvent.conversation_id)
        .where(
            Conversation.user_id == user_id,
            FinancialEvent.status.in_(
                [
                    FinancialEventStatus.AWAITING_CONFIRMATION,
                    FinancialEventStatus.NEEDS_CLARIFICATION,
                    FinancialEventStatus.FAILED,
                ]
            ),
        )
    )

    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                FinancialEvent.raw_text.ilike(pattern),
                Conversation.title.ilike(pattern),
            )
        )
    if date_from:
        query = query.where(FinancialEvent.created_at >= date_from)
    if date_to:
        query = query.where(FinancialEvent.created_at < date_to)

    total = int(await db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    result = await db.execute(
        query.order_by(FinancialEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.all()), total


async def update_financial_event(db: AsyncSession, event: FinancialEvent) -> FinancialEvent:
    await db.flush()
    return event


async def get_pending_event_by_conversation(db, conversation_id):
    result = await db.execute(
        select(FinancialEvent)
        .where(
            FinancialEvent.conversation_id == conversation_id,
            FinancialEvent.status == FinancialEventStatus.NEEDS_CLARIFICATION,
        )
        .order_by(FinancialEvent.created_at.desc())
    )
    # A completed parse is also stored as NEEDS_CLARIFICATION while waiting for
    # explicit confirmation, but it must not hijack the next unrelated chat
    # message. Only events that still have missing fields are conversationally
    # pending.
    return next((event for event in result.scalars() if event.missing_fields), None)
