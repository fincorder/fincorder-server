import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.conversations import repository as conversations_repository
from app.modules.financial_events import repository
from app.modules.financial_events.models import FinancialEvent, FinancialEventStatus
from app.modules.messages import repository as messages_repository


async def create_financial_event(db: AsyncSession, conversation_id: uuid.UUID, source_message_id: uuid.UUID, user_id: uuid.UUID, raw_text: str) -> FinancialEvent:
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


async def mark_processing(db: AsyncSession, event: FinancialEvent) -> FinancialEvent:
    event.status = FinancialEventStatus.PROCESSING
    await repository.update_financial_event(db, event)
    await db.commit()
    return event


async def mark_completed(db: AsyncSession, event: FinancialEvent, extracted_data: dict) -> FinancialEvent:
    event.status = FinancialEventStatus.COMPLETED
    event.extracted_data = extracted_data
    event.missing_fields = []

    await repository.update_financial_event(db, event)
    await db.commit()

    return event


async def mark_needs_clarification(db: AsyncSession, event: FinancialEvent, missing_fields: list) -> FinancialEvent:
    event.status = FinancialEventStatus.NEEDS_CLARIFICATION
    event.missing_fields = missing_fields

    await repository.update_financial_event(db, event)
    await db.commit()

    return event


async def mark_failed(db: AsyncSession, event: FinancialEvent, error: str) -> FinancialEvent:
    event.status = FinancialEventStatus.FAILED
    event.error = error

    await repository.update_financial_event(db, event)
    await db.commit()

    return event


async def get_pending_event_by_conversation(db: AsyncSession, conversation_id: uuid.UUID):
    return await repository.get_pending_event_by_conversation(db, conversation_id)