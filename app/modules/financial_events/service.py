import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.conversations import repository as conversations_repository
from app.modules.financial_events import repository
from app.modules.financial_events.models import FinancialEvent, FinancialEventStatus
from app.modules.messages import repository as messages_repository
from app.modules.users.models import User


def _month_bounds(month: str, timezone_name: str | None) -> tuple[datetime, datetime]:
    try:
        year, month_number = (int(value) for value in month.split("-"))
        if len(month) != 7 or month[4] != "-" or not 1 <= month_number <= 12:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("month must use YYYY-MM format") from None

    try:
        zone = ZoneInfo(timezone_name or "UTC")
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("UTC")

    start = datetime(year, month_number, 1, tzinfo=zone)
    if month_number == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=zone)
    else:
        next_month = datetime(year, month_number + 1, 1, tzinfo=zone)
    return start.astimezone(timezone.utc), next_month.astimezone(timezone.utc)


async def create_financial_event(db: AsyncSession, conversation_id: uuid.UUID, source_message_id: uuid.UUID, user_id: uuid.UUID, raw_text: str, commit: bool = True) -> FinancialEvent:
    conversation = await conversations_repository.get_conversation_by_id(db, conversation_id, user_id)
    if not conversation:
        raise ValueError("Conversation not found")

    message = await messages_repository.get_message_by_id(db, source_message_id)
    if not message or message.conversation_id != conversation_id:
        raise ValueError("Message not found")

    event = FinancialEvent(
        conversation_id=conversation_id,
        source_message_id=source_message_id,
        raw_text=raw_text,
        status=FinancialEventStatus.PENDING,
    )

    await repository.create_financial_event(db, event)
    if commit:
        await db.commit()

    return event


async def get_financial_event(db: AsyncSession, event_id: uuid.UUID, user_id: uuid.UUID) -> FinancialEvent:
    event = await repository.get_financial_event_by_id(db, event_id)
    if not event:
        raise ValueError("Financial event not found")

    conversation = await conversations_repository.get_conversation_by_id(db, event.conversation_id, user_id)
    if not conversation:
        raise ValueError("Financial event not found")

    return event


async def get_financial_events(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> list[FinancialEvent]:
    conversation = await conversations_repository.get_conversation_by_id(db, conversation_id, user_id)
    if not conversation:
        raise ValueError("Conversation not found")

    return await repository.get_financial_events_by_conversation(db, conversation_id)


async def get_review_events_page(
    db: AsyncSession,
    user: User,
    *,
    limit: int = 25,
    offset: int = 0,
    search: str | None = None,
    month: str | None = None,
) -> dict:
    date_from = date_to = None
    if month:
        date_from, date_to = _month_bounds(month, user.timezone)

    events, total = await repository.get_review_events_page(
        db,
        user.id,
        limit=limit,
        offset=offset,
        search=search.strip() if search else None,
        date_from=date_from,
        date_to=date_to,
    )
    items = [
        {
            "id": event.id,
            "conversation_id": event.conversation_id,
            "conversation_title": title,
            "source_message_id": event.source_message_id,
            "status": event.status.value,
            "raw_text": event.raw_text,
            "extracted_data": event.extracted_data,
            "missing_fields": event.missing_fields,
            "error": event.error,
            "assistant_message_id": event.assistant_message_id,
            "revision": event.revision,
            "created_at": event.created_at,
            "updated_at": event.updated_at,
        }
        for event, title in events
    ]
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_next": offset + len(items) < total,
    }


async def mark_processing(db: AsyncSession, event: FinancialEvent, commit: bool = True) -> FinancialEvent:
    event.status = FinancialEventStatus.PROCESSING
    await repository.update_financial_event(db, event)
    if commit:
        await db.commit()
    return event


async def mark_completed(db: AsyncSession, event: FinancialEvent, extracted_data: dict, commit: bool = True) -> FinancialEvent:
    event.status = FinancialEventStatus.COMPLETED
    event.extracted_data = extracted_data
    event.missing_fields = []

    await repository.update_financial_event(db, event)
    if commit:
        await db.commit()

    return event


async def mark_needs_clarification(
    db: AsyncSession,
    event: FinancialEvent,
    missing_fields: list,
    extracted_data: dict | None = None,
    commit: bool = True,
) -> FinancialEvent:
    event.status = FinancialEventStatus.NEEDS_CLARIFICATION
    event.missing_fields = missing_fields
    if extracted_data is not None:
        event.extracted_data = extracted_data

    await repository.update_financial_event(db, event)
    if commit:
        await db.commit()

    return event


async def mark_failed(db: AsyncSession, event: FinancialEvent, error: str, commit: bool = True) -> FinancialEvent:
    event.status = FinancialEventStatus.FAILED
    event.error = error

    await repository.update_financial_event(db, event)
    if commit:
        await db.commit()

    return event


async def get_pending_event_by_conversation(db: AsyncSession, conversation_id: uuid.UUID):
    return await repository.get_pending_event_by_conversation(db, conversation_id)
