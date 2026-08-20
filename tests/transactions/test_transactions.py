from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from app.modules.financial_events.service import create_financial_event
from app.modules.transaction_groups.service import create_transaction_group


async def register_and_login(client):
    await client.post(
        "/auth/register",
        json={
            "name": "Aashir",
            "email": "aashir@example.com",
            "password": "password123",
        },
    )

    login = await client.post(
        "/auth/login",
        json={
            "email": "aashir@example.com",
            "password": "password123",
        },
    )

    return login.json()["access_token"]


async def setup_dependencies(client, db_session, token):
    user = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = UUID(user.json()["id"])

    conversation = await client.post(
        "/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Test"},
    )
    conversation_id = UUID(conversation.json()["id"])

    message = await client.post(
        f"/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Paid ₹500 for petrol"},
    )

    event = await create_financial_event(
        db=db_session,
        conversation_id=conversation_id,
        source_message_id=UUID(message.json()["id"]),
        user_id=user_id,
        raw_text="Paid ₹500 for petrol",
    )

    group = await create_transaction_group(
        db=db_session,
        financial_event_id=event.id,
    )

    accounts = await client.get(
        "/accounts",
        headers={"Authorization": f"Bearer {token}"},
    )
    account_id = accounts.json()[0]["id"]

    categories = await client.get(
        "/categories",
        headers={"Authorization": f"Bearer {token}"},
    )
    category_id = next(
        c["id"] for c in categories.json() if c["name"] == "Food"
    )

    return group.id, account_id, category_id


@pytest.mark.asyncio
async def test_create_transaction(client, db_session):
    token = await register_and_login(client)
    group_id, account_id, category_id = await setup_dependencies(
        client,
        db_session,
        token,
    )

    response = await client.post(
        "/transactions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_group_id": str(group_id),
            "account_id": account_id,
            "category_id": category_id,
            "type": "expense",
            "direction": "debit",
            "amount": "500.00",
            "currency": "INR",
            "description": "Petrol",
            "transaction_date": datetime.now(
                timezone.utc
            ).isoformat(),
        },
    )

    assert response.status_code == 201
    assert Decimal(response.json()["amount"]) == Decimal("500.00")