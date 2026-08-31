from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    return result.scalars().first()