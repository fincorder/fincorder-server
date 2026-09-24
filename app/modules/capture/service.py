from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas import AITransaction
from app.modules.capture.context_builder import build_capture_context
from app.modules.capture.execution import apply_transactions, validate_transactions
from app.modules.capture.helpers import extract_correction_target_amount, extract_explicit_amount
from app.modules.capture.models import CaptureReceipt
from app.modules.capture.schemas import CaptureResponse
from app.modules.capture.state import prepare_response, starts_new_transaction, validation_missing_field
from app.modules.conversations import repository as conversations_repository
from app.modules.conversations.models import Conversation
from app.modules.financial_events.models import FinancialEvent, FinancialEventStatus as Status
from app.modules.financial_events import service as events_service
from app.modules.messages import repository as messages_repository
from app.modules.messages.models import Message
from app.modules.transactions import repository as transactions_repository
from app.modules.transactions.models import Transaction
from app.modules.users.models import User


async def lock_user(db, user):
    # Serialize capture/confirm/reject across tabs, always locking user before events.
    return await db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))


def result_message(transactions):
    counts = {operation: sum(t.operation == operation for t in transactions) for operation in ("create", "update", "delete")}
    return "; ".join(f"{label} {counts[operation]} transaction{'s' if counts[operation] != 1 else ''}" for operation, label in (("create", "Added"), ("update", "Updated"), ("delete", "Archived")) if counts[operation]) + "."


async def search_transactions(db, user, arguments):
    if set(arguments) - {"search", "date_from", "date_to"}:
        raise ValueError("Unsupported search filter")
    filters = {k: v for k, v in arguments.items() if v}
    for key in ("date_from", "date_to"):
        if key in filters:
            from app.modules.capture.execution import local_date
            filters[key] = local_date(filters[key], user.timezone)
    items = await transactions_repository.get_transactions(db, user.id, limit=20, **filters)
    return [{"id": str(t.id), "amount": str(t.amount), "currency": t.currency, "type": t.type.value, "direction": t.direction.value, "description": t.description, "date": t.transaction_date.isoformat(), "account": t.account.name, "category": t.category.name if t.category else None, "person": t.person.name if t.person else None} for t in items]


async def capture_message(db: AsyncSession, user, message: str, conversation_id, ai_provider, request_id=None, financial_event_id=None) -> CaptureResponse:
    try:
        user = await lock_user(db, user)
        fingerprint = hashlib.sha256(json.dumps([message, str(conversation_id), str(financial_event_id)]).encode()).hexdigest()
        if request_id:
            receipt = await db.get(CaptureReceipt, (user.id, request_id))
            if receipt:
                if receipt.fingerprint != fingerprint:
                    raise ValueError("This request ID was already used for a different message")
                return CaptureResponse.model_validate(receipt.response)
        if conversation_id:
            conversation = await conversations_repository.get_conversation_by_id(db, conversation_id, user.id)
            if not conversation:
                raise ValueError("Conversation not found or archived")
        else:
            conversation = Conversation(user_id=user.id, title="New Chat")
            await conversations_repository.create_conversation(db, conversation)
        user_message = Message(conversation_id=conversation.id, role="user", content=message.strip())
        await messages_repository.create_message(db, user_message)
        pending_events = list(await db.scalars(select(FinancialEvent).where(FinancialEvent.conversation_id == conversation.id, FinancialEvent.status.in_([Status.NEEDS_CLARIFICATION, Status.AWAITING_CONFIRMATION])).order_by(FinancialEvent.updated_at.desc())))
        selected = next((e for e in pending_events if e.id == financial_event_id), None)
        if financial_event_id and not selected:
            raise ValueError("The selected draft is no longer pending")
        context = await build_capture_context(db, user.id, conversation.id, timezone_name=user.timezone)
        context["review_transactions"] = user.review_transactions
        context["pending_events"] = [{"id": str(e.id), "status": e.status.value, "transactions": (e.extracted_data or {}).get("transactions", []), "missing_fields": e.missing_fields or []} for e in pending_events[:10]]
        if selected:
            context["selected_event_id"] = str(selected.id)
            if selected not in pending_events[:10]:
                context["pending_events"].append({"id": str(selected.id), "status": selected.status.value, "transactions": (selected.extracted_data or {}).get("transactions", []), "missing_fields": selected.missing_fields or []})
        from app.ai.openai_provider import OpenAIProvider
        if isinstance(ai_provider, OpenAIProvider):
            response = await ai_provider.extract_financial_event(message, context, search_tool=lambda args: search_transactions(db, user, args))
        else:
            response = await ai_provider.extract_financial_event(message=message, context=context)
        if response.continuation_event_id:
            chosen = next((e for e in pending_events if e.id == response.continuation_event_id), None)
            if chosen is None or (selected and chosen.id != selected.id):
                raise ValueError("The AI selected an invalid draft")
            selected = chosen
        clarifications = [e for e in pending_events if e.status == Status.NEEDS_CLARIFICATION]
        if not selected and not isinstance(ai_provider, OpenAIProvider) and len(clarifications) == 1 and not starts_new_transaction(message):
            selected = clarifications[0]
        if not selected and len(clarifications) > 1 and not starts_new_transaction(message) and not response.transactions:
            response = response.model_copy(update={"status": "needs_clarification", "assistant_message": "Choose Resume on the draft you want to continue.", "missing_fields": ["draft"]})
        old_amount, new_amount = extract_correction_target_amount(message), extract_explicit_amount(message)
        if not selected and old_amount is not None and new_amount is not None and old_amount != new_amount:
            candidates = list(await db.scalars(select(Transaction.id).where(Transaction.user_id == user.id, Transaction.deleted_at.is_(None), Transaction.amount == old_amount).limit(2)))
            has_target = any(t.transaction_id for t in response.transactions)
            if len(candidates) == 1 and not has_target:
                response = response.model_copy(update={"status": "completed", "transactions": [AITransaction(operation="update", transaction_id=candidates[0], amount=new_amount)], "missing_fields": []})
            elif len(candidates) > 1 and not has_target:
                response = response.model_copy(update={"status": "needs_clarification", "transactions": [], "missing_fields": ["transaction_id"], "assistant_message": "Several transactions have that amount. Which description and date should I change?"})
        response = prepare_response(response, message, context, selected)
        event = selected or await events_service.create_financial_event(db, conversation.id, user_message.id, user.id, message, commit=False)
        if selected:
            event.revision += 1
        data = response.model_dump(mode="json")
        event.error = None
        ids, versions = [], {}
        validation_error = None
        if response.status == "failed" and selected:
            data = dict(selected.extracted_data or {})
            assistant_text = "I couldn't understand that reply. Your draft is still saved; please try again or edit its details."
        elif response.status == "completed" and response.transactions:
            try:
                _, versions = await validate_transactions(db, user, response.transactions)
            except ValueError as exc:
                validation_error = str(exc)
            requires_review = user.review_transactions or (selected is not None and selected.status == Status.AWAITING_CONFIRMATION)
            if not requires_review and validation_error is None:
                ids, before = await apply_transactions(db, user, event, response.transactions, versions)
                event.status = Status.COMPLETED
                assistant_text = result_message(response.transactions)
                data.update(transaction_ids=[str(i) for i in ids], before=before, mode="automatic", result_message=assistant_text)
            elif not requires_review and validation_error:
                event.status = Status.NEEDS_CLARIFICATION
                event.missing_fields = [validation_missing_field(validation_error)]
                assistant_text = validation_error + " Please clarify so I can finish this transaction."
                data.update(validation_error=validation_error, mode="automatic")
            else:
                event.status = Status.AWAITING_CONFIRMATION
                assistant_text = "Review the transaction details below, then confirm the changes."
                if validation_error:
                    assistant_text = f"{validation_error} Edit this draft or reply with the missing details."
                data.update(target_versions=versions, mode="review", validation_error=validation_error)
            if event.status != Status.NEEDS_CLARIFICATION:
                event.missing_fields = []
        elif response.status == "needs_clarification":
            event.status = Status.NEEDS_CLARIFICATION
            event.missing_fields = response.missing_fields or ["details"]
            assistant_text = response.assistant_message
            if len(response.transactions) == 1 and response.transactions[0].amount is not None:
                t = response.transactions[0]
                amount_label = f"{t.currency or 'INR'} {t.amount}"
                if "person" in event.missing_fields and t.type == "lend":
                    assistant_text = f"Who did you lend {amount_label} to?"
                elif "person" in event.missing_fields and t.type == "borrow":
                    assistant_text = f"Who did you borrow {amount_label} from?"
                elif set(event.missing_fields).intersection({"category", "description"}):
                    assistant_text = f"What was the {amount_label} for?"
                elif "account" in event.missing_fields:
                    assistant_text = f"Which account did you use for the {amount_label}?"
        else:
            event.status = Status.FAILED
            event.missing_fields = []
            assistant_text = "I couldn't extract a transaction. Please describe the amount and what happened."
            event.error = response.assistant_message
        event.extracted_data = data
        assistant = Message(conversation_id=conversation.id, role="assistant", content=assistant_text)
        await messages_repository.create_message(db, assistant)
        event.assistant_message_id = assistant.id
        conversation.updated_at = datetime.now(timezone.utc)
        result = CaptureResponse(conversation_id=conversation.id, message_id=user_message.id, assistant_message_id=assistant.id, financial_event_id=event.id, status=event.status.value, assistant_message=assistant_text, needs_clarification=event.status == Status.NEEDS_CLARIFICATION, missing_fields=event.missing_fields, awaiting_confirmation=event.status == Status.AWAITING_CONFIRMATION, proposed_transactions=response.transactions, transaction_ids=ids, revision=event.revision)
        if request_id:
            db.add(CaptureReceipt(user_id=user.id, request_id=request_id, fingerprint=fingerprint, response=result.model_dump(mode="json")))
        await db.commit()
        return result
    except Exception:
        await db.rollback()
        raise


async def get_locked_event(db, user, event_id):
    await lock_user(db, user)
    return await events_service.get_financial_event(db, event_id, user.id)


def confirmation_result(event):
    return {"financial_event_id": event.id, "status": event.status.value, "assistant_message": (event.extracted_data or {}).get("result_message", "Transaction changes saved."), "transaction_ids": (event.extracted_data or {}).get("transaction_ids", []), "revision": event.revision}


def check_revision(event, revision):
    if event.revision != revision:
        raise ValueError("This draft has changed. Reload the chat before continuing.")


def check_proposal_scope(event, transactions):
    original = (event.extracted_data or {}).get("transactions", [])
    if len(original) != len(transactions):
        raise ValueError("The number of proposed operations cannot be changed")
    for stored, submitted in zip(original, transactions):
        if stored.get("operation", "create") != submitted.operation or stored.get("transaction_id") != (str(submitted.transaction_id) if submitted.transaction_id else None):
            raise ValueError("A proposal's operation and target cannot be changed")


async def confirm_capture(db, financial_event_id, user, transactions, revision=1):
    try:
        event = await get_locked_event(db, user, financial_event_id)
        if event.status == Status.COMPLETED:
            return confirmation_result(event)
        if event.status != Status.AWAITING_CONFIRMATION:
            raise ValueError("This capture is not ready for confirmation")
        check_revision(event, revision)
        check_proposal_scope(event, transactions)
        ids, before = await apply_transactions(db, user, event, transactions, (event.extracted_data or {}).get("target_versions"))
        text = result_message(transactions)
        event.extracted_data = {**(event.extracted_data or {}), "transactions": [t.model_dump(mode="json") for t in transactions], "transaction_ids": [str(i) for i in ids], "before": before, "result_message": text}
        event.status = Status.COMPLETED
        event.revision += 1
        if event.assistant_message_id:
            assistant = await messages_repository.get_message_by_id(db, event.assistant_message_id)
            if assistant:
                assistant.content = text
        await db.commit()
        return confirmation_result(event)
    except Exception:
        await db.rollback()
        raise


async def save_capture_draft(db, financial_event_id, user, transactions, revision):
    try:
        event = await get_locked_event(db, user, financial_event_id)
        if event.status != Status.AWAITING_CONFIRMATION:
            raise ValueError("Only a pending review can be edited")
        check_revision(event, revision)
        check_proposal_scope(event, transactions)
        event.extracted_data = {**(event.extracted_data or {}), "transactions": [t.model_dump(mode="json") for t in transactions]}
        event.revision += 1
        await db.commit()
        return {"financial_event_id": event.id, "status": event.status.value, "assistant_message": "Draft saved.", "revision": event.revision}
    except Exception:
        await db.rollback()
        raise


async def reject_capture(db, financial_event_id, user):
    try:
        event = await get_locked_event(db, user, financial_event_id)
        if event.status == Status.REJECTED:
            return confirmation_result(event)
        if event.status not in {Status.NEEDS_CLARIFICATION, Status.AWAITING_CONFIRMATION}:
            raise ValueError("This capture is no longer pending")
        event.status = Status.REJECTED
        event.revision += 1
        event.extracted_data = {**(event.extracted_data or {}), "result_message": "Proposal rejected. Nothing was changed."}
        if event.assistant_message_id:
            assistant = await messages_repository.get_message_by_id(db, event.assistant_message_id)
            if assistant:
                assistant.content = "Proposal rejected. Nothing was changed."
        await db.commit()
        return confirmation_result(event)
    except Exception:
        await db.rollback()
        raise
