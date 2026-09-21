from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas import CaptureAIResponse
from app.modules.capture.context_builder import build_capture_context
from app.modules.capture.helpers import parse_transaction_date, resolve_account_id, resolve_category_id, resolve_person_id
from app.modules.capture.schemas import CaptureResponse
from app.modules.conversations import repository as conversations_repository
from app.modules.conversations.models import Conversation, ConversationStatus
from app.modules.financial_events import service as financial_events_service
from app.modules.messages import repository as messages_repository
from app.modules.messages.models import Message
from app.modules.transaction_groups import service as transaction_groups_service
from app.modules.transactions import service as transactions_service
from app.modules.transactions.models import TransactionDirection, TransactionType


async def capture_message(db: AsyncSession, user, message: str, conversation_id, ai_provider) -> CaptureResponse:
    try:
        # 1. Get or create conversation
        if conversation_id:
            conversation = await conversations_repository.get_conversation_by_id(db, conversation_id, user.id)
            if not conversation or conversation.status == ConversationStatus.ARCHIVED:
                raise ValueError("Conversation not found or archived")
        else:
            conversation = Conversation(user_id=user.id, title="New Chat")
            await conversations_repository.create_conversation(db, conversation)

        # 2. Save user message
        user_message = Message(conversation_id=conversation.id, role="user", content=message)
        await messages_repository.create_message(db, user_message)
        conversation.updated_at = datetime.now(timezone.utc)
        await db.flush()

        # 3. Check for an existing clarification event
        pending_event = await financial_events_service.get_pending_event_by_conversation(db=db, conversation_id=conversation.id)

        # 4. Build context
        context = await build_capture_context(db=db, user_id=user.id, conversation_id=conversation.id)

        # 5. AI extraction
        ai_response = await ai_provider.extract_financial_event(message=message, context=context)

        # 6. Continue an existing clarification event or create a new event
        if pending_event:
            financial_event = pending_event
        else:
            financial_event = await financial_events_service.create_financial_event(
                db=db,
                conversation_id=conversation.id,
                source_message_id=user_message.id,
                user_id=user.id,
                raw_text=message,
                commit=False,
            )

        # 7. Process AI response
        needs_clarification = await process_ai_response(
            db=db,
            user=user,
            financial_event=financial_event,
            ai_response=ai_response,
        )

        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=ai_response.assistant_message,
        )
        await messages_repository.create_message(db, assistant_message)
        conversation.updated_at = datetime.now(timezone.utc)
        await db.commit()

        return CaptureResponse(
            conversation_id=conversation.id,
            message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            financial_event_id=financial_event.id,
            status=ai_response.status,
            assistant_message=ai_response.assistant_message,
            needs_clarification=needs_clarification,
            missing_fields=ai_response.missing_fields,
        )
    except Exception:
        await db.rollback()
        raise


async def process_ai_response(db: AsyncSession, user, financial_event, ai_response: CaptureAIResponse) -> bool:
    """Process the AI response. Returns True if clarification is required."""

    if ai_response.status == "needs_clarification":
        await financial_events_service.mark_needs_clarification(db=db, event=financial_event, missing_fields=ai_response.missing_fields, commit=False)
        return True

    if ai_response.status == "failed":
        await financial_events_service.mark_failed(db=db, event=financial_event, error=ai_response.assistant_message, commit=False)
        return False

    create_transactions = [transaction for transaction in ai_response.transactions if transaction.operation == "create"]
    transaction_group = None
    if create_transactions:
        transaction_group = await transaction_groups_service.create_transaction_group(db=db, financial_event_id=financial_event.id, commit=False)

    for txn in ai_response.transactions:
        if txn.operation == "delete":
            if not txn.transaction_id:
                raise ValueError("Transaction id is required for deletion")
            await transactions_service.delete_transaction(db, txn.transaction_id, user.id, commit=False)
            continue

        if txn.operation == "update":
            if not txn.transaction_id:
                raise ValueError("Transaction id is required for update")

            updates = {}
            for field in ("type", "direction", "amount", "currency", "description", "transaction_date"):
                value = getattr(txn, field)
                if value is not None:
                    updates[field] = value

            if txn.account:
                updates["account_id"] = await resolve_account_id(db, user.id, txn.account)
            if txn.category:
                category_id = await resolve_category_id(db, user.id, txn.category)
                if category_id is None:
                    raise ValueError(f"Category '{txn.category}' not found")
                updates["category_id"] = category_id
            if txn.person:
                person_id = await resolve_person_id(db, user.id, txn.person)
                if person_id is None:
                    raise ValueError(f"Person '{txn.person}' not found")
                updates["person_id"] = person_id

            for field in txn.clear_fields:
                if field in {"category", "person", "description"}:
                    updates[
                        {
                            "category": "category_id",
                            "person": "person_id",
                            "description": "description",
                        }[field]
                    ] = None

            if not updates:
                raise ValueError("At least one transaction field is required for update")

            if "type" in updates:
                updates["type"] = TransactionType(updates["type"])
            if "direction" in updates:
                updates["direction"] = TransactionDirection(updates["direction"])
            if "transaction_date" in updates:
                updates["transaction_date"] = parse_transaction_date(updates["transaction_date"])

            await transactions_service.update_transaction(db, txn.transaction_id, user.id, commit=False, **updates)
            continue

        if txn.type is None or txn.amount is None or txn.direction is None:
            raise ValueError("Transaction type, amount, and direction are required")

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
            transaction_date=parse_transaction_date(txn.transaction_date) if txn.transaction_date else datetime.now(timezone.utc),
            commit=False,
        )

    if transaction_group:
        await transaction_groups_service.mark_posted(db=db, transaction_group=transaction_group, commit=False)
    await financial_events_service.mark_completed(db=db, event=financial_event, extracted_data=ai_response.model_dump(mode="json"), commit=False)

    return False
