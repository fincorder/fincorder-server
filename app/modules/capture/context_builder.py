from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts import repository as accounts_repository
from app.modules.categories import repository as categories_repository
from app.modules.people import repository as people_repository
from app.modules.messages import repository as messages_repository
from app.modules.transactions import repository as transactions_repository


async def build_capture_context(db: AsyncSession, user_id, conversation_id=None) -> dict:
    accounts = await accounts_repository.get_accounts(db, user_id)
    categories = await categories_repository.get_categories(db, user_id)
    people = await people_repository.get_people(db, user_id)
    transactions = await transactions_repository.get_transactions(db, user_id)

    context = {
        "today": datetime.now(timezone.utc).date().isoformat(),
        "accounts": [a.name for a in accounts],
        "categories": [c.name for c in categories],
        "people": [p.name for p in people],
        "messages": [],
        "transactions": [
            {
                "id": str(transaction.id),
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
        messages = await messages_repository.get_messages(db, conversation_id)

        context["messages"] = [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in messages[:-1][-10:]
        ]

    return context
