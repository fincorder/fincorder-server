from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.openai_provider import OpenAIProvider
from app.modules.capture.context_builder import build_capture_context
from app.modules.capture.schemas import CaptureResponse
from app.modules.capture.helpers import resolve_account_id, resolve_category_id, resolve_person_id
from app.modules.conversations import repository as conversations_repository
from app.modules.conversations.models import Conversation
from app.modules.financial_events import service as financial_events_service
from app.modules.messages import repository as messages_repository
from app.modules.messages.models import Message
from app.modules.transaction_groups import service as transaction_groups_service
from app.modules.transactions import service as transactions_service
from app.modules.transactions.models import TransactionDirection, TransactionType

def get_ai_provider():
    return OpenAIProvider()


async def capture_message(db: AsyncSession, user, message: str, conversation_id=None, ai_provider=None) -> CaptureResponse:
    ai_provider = ai_provider or get_ai_provider()

    # Conversation
    if conversation_id:
        conversation = await conversations_repository.get_conversation_by_id(db, conversation_id, user.id)
        if not conversation:
            raise ValueError("Conversation not found")
    else:
        conversation = Conversation(user_id=user.id, title="New Chat")
        await conversations_repository.create_conversation(db, conversation)
        await db.commit()

    # User message
    user_message = Message(conversation_id=conversation.id, role="user", content=message)
    await messages_repository.create_message(db, user_message)
    await db.commit()

    # Financial event
    financial_event = await financial_events_service.create_financial_event(
        db=db,
        conversation_id=conversation.id,
        source_message_id=user_message.id,
        user_id=user.id,
        raw_text=message,
    )

    # Context
    context = await build_capture_context(db, user.id)

    # AI extraction
    ai_response = await ai_provider.extract_financial_event(message=message, context=context)

    # Clarification
    if ai_response.status == "needs_clarification":
        await financial_events_service.mark_needs_clarification(db=db, event=financial_event, missing_fields=ai_response.missing_fields)

        return CaptureResponse(
            conversation_id=conversation.id,
            message_id=user_message.id,
            financial_event_id=financial_event.id,
            status=ai_response.status,
            assistant_message=ai_response.assistant_message,
            needs_clarification=True,
            missing_fields=ai_response.missing_fields,
        )

    # Transaction group
    transaction_group = await transaction_groups_service.create_transaction_group(db=db, financial_event_id=financial_event.id)

    # Transactions
    for txn in ai_response.transactions:
        await transactions_service.create_transaction(
            db=db,
            transaction_group_id=transaction_group.id,
            user_id=user.id,
            account_id=await resolve_account_id(db, user.id, txn.account),
            category_id=await resolve_category_id(db, user.id, txn.category),
            person_id=await resolve_person_id(db, user.id, txn.person),
            transaction_type=TransactionType(txn.type),
            direction=TransactionDirection(txn.direction),
            amount=txn.amount,
            currency=txn.currency,
            description=txn.description,
            transaction_date=(
                datetime.fromisoformat(txn.transaction_date)
                if txn.transaction_date
                else datetime.now(timezone.utc)
            ),
        )

    await transaction_groups_service.mark_posted(db=db, transaction_group=transaction_group)
    await financial_events_service.mark_completed(db=db, event=financial_event, extracted_data=ai_response.model_dump(mode="json"))

    return CaptureResponse(
        conversation_id=conversation.id,
        message_id=user_message.id,
        financial_event_id=financial_event.id,
        status=ai_response.status,
        assistant_message=ai_response.assistant_message,
        needs_clarification=False,
        missing_fields=[],
    )