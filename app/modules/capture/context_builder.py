from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts import repository as accounts_repository
from app.modules.categories import repository as categories_repository
from app.modules.people import repository as people_repository
from app.modules.transactions import repository as transactions_repository
from app.modules.messages.models import Message


async def build_capture_context(db: AsyncSession, user_id, conversation_id=None, pending_event=None, timezone_name="UTC") -> dict:
    accounts = await accounts_repository.get_accounts(db, user_id)
    categories = await categories_repository.get_categories(db, user_id)
    people = await people_repository.get_people(db, user_id)
    transactions = await transactions_repository.get_transactions(db, user_id, limit=20)
    default_account = next(
        (account for account in accounts if account.is_default),
        next((account for account in accounts if account.name.lower() == "spending account"), accounts[0] if accounts else None),
    )

    context = {
        "today": datetime.now(ZoneInfo(timezone_name)).date().isoformat(),
        "timezone": timezone_name,
        "accounts": [a.name for a in accounts],
        "account_details": [{"name": a.name, "currency": a.currency} for a in accounts],
        "default_account": default_account.name if default_account else None,
        "categories": [c.name for c in categories],
        "people": [p.name for p in people],
        "messages": [],
        "pending_event": None,
        "transactions": [
            {
                "id": str(transaction.id),
                "transaction_group_id": str(transaction.transaction_group_id),
                "direction": transaction.direction.value,
                "type": transaction.type.value,
                "amount": str(transaction.amount),
                "currency": transaction.currency,
                "account": transaction.account.name if transaction.account else None,
                "category": transaction.category.name if transaction.category else None,
                "person": transaction.person.name if transaction.person else None,
                "description": transaction.description,
                "transaction_date": transaction.transaction_date.isoformat(),
            }
            for transaction in transactions[:20]
        ],
    }

    if conversation_id:
        result = await db.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.desc(), Message.id.desc()).limit(11))
        messages = list(reversed(result.all()))

        context["messages"] = [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in messages[:-1][-10:]
        ]

    if pending_event:
        context["pending_event"] = {
            "raw_text": pending_event.raw_text,
            "extracted_data": pending_event.extracted_data,
            "missing_fields": pending_event.missing_fields or [],
        }

    return context
