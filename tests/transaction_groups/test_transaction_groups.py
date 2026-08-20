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


async def create_conversation(client, token):
    response = await client.post(
        "/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Test Chat"},
    )
    return response.json()["id"]


async def create_message(client, token, conversation_id):
    response = await client.post(
        f"/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Paid ₹500 for petrol"},
    )
    return response.json()


@pytest.mark.asyncio
async def test_get_transaction_group(client, db_session):
    token = await register_and_login(client)
    conversation_id = UUID(await create_conversation(client, token))
    message = await create_message(client, token, str(conversation_id))

    user = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = UUID(user.json()["id"])

    event = await create_financial_event(
        db=db_session,
        conversation_id=conversation_id,
        source_message_id=UUID(message["id"]),
        user_id=user_id,
        raw_text=message["content"],
    )

    group = await create_transaction_group(
        db=db_session,
        financial_event_id=event.id,
    )

    response = await client.get(
        f"/transaction-groups/{group.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_get_transaction_groups_by_event(client, db_session):
    token = await register_and_login(client)
    conversation_id = UUID(await create_conversation(client, token))
    message = await create_message(client, token, str(conversation_id))

    user = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = UUID(user.json()["id"])

    event = await create_financial_event(
        db=db_session,
        conversation_id=conversation_id,
        source_message_id=UUID(message["id"]),
        user_id=user_id,
        raw_text=message["content"],
    )

    await create_transaction_group(
        db=db_session,
        financial_event_id=event.id,
    )

    response = await client.get(
        f"/transaction-groups/event/{event.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_transaction_group_not_found(client):
    token = await register_and_login(client)

    response = await client.get(
        "/transaction-groups/11111111-1111-1111-1111-111111111111",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404