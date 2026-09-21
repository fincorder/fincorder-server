from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.ai.schemas import AITransaction, CaptureAIResponse
from app.main import app
from app.modules.capture.dependencies import get_ai_provider


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


@pytest.mark.asyncio
async def test_capture_creates_transaction(client):
    token = await register_and_login(client)

    ai_response = CaptureAIResponse(
        status="completed",
        transactions=[
            AITransaction(
                type="expense",
                amount=500,
                currency="INR",
                account="Spending Account",
                category="Transport",
                person=None,
                description="Petrol",
                transaction_date=None,
                direction="debit",
            )
        ],
        missing_fields=[],
        assistant_message="Recorded your ₹500 petrol expense.",
        confidence=0.99,
    )

    provider = AsyncMock()
    provider.extract_financial_event.return_value = ai_response

    app.dependency_overrides[get_ai_provider] = lambda: provider

    try:
        response = await client.post(
            "/capture",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "message": "Paid ₹500 for petrol",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["status"] == "completed"
        assert data["needs_clarification"] is False
        assert data["missing_fields"] == []
        assert data["assistant_message"] == "Recorded your ₹500 petrol expense."
        assert data["conversation_id"] is not None
        assert data["message_id"] is not None
        assert data["financial_event_id"] is not None

        provider.extract_financial_event.assert_awaited_once()

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_capture_needs_clarification(client):
    token = await register_and_login(client)

    ai_response = CaptureAIResponse(
        status="needs_clarification",
        transactions=[],
        missing_fields=["category"],
        assistant_message="What was the ₹500 for?",
        confidence=0.95,
    )

    provider = AsyncMock()
    provider.extract_financial_event.return_value = ai_response

    app.dependency_overrides[get_ai_provider] = lambda: provider

    try:
        response = await client.post(
            "/capture",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "message": "Paid ₹500",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["status"] == "needs_clarification"
        assert data["needs_clarification"] is True
        assert data["missing_fields"] == ["category"]
        assert data["assistant_message"] == "What was the ₹500 for?"
        assert data["financial_event_id"] is not None

        provider.extract_financial_event.assert_awaited_once()

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_capture_requires_auth(client):
    response = await client.post(
        "/capture",
        json={
            "message": "Paid ₹500 for petrol",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_capture_clarification_flow(client):
    token = await register_and_login(client)

    first_response = CaptureAIResponse(
        status="needs_clarification",
        transactions=[],
        missing_fields=["category"],
        assistant_message="What was the ₹500 for?",
        confidence=0.95,
    )

    second_response = CaptureAIResponse(
        status="completed",
        transactions=[
            AITransaction(
                type="expense",
                amount=500,
                currency="INR",
                account="Spending Account",
                category="Transport",
                person=None,
                description="Petrol",
                transaction_date=None,
                direction="debit",
            )
        ],
        missing_fields=[],
        assistant_message="Recorded your ₹500 petrol expense.",
        confidence=0.98,
    )

    provider = AsyncMock()
    provider.extract_financial_event.side_effect = [
        first_response,
        second_response,
    ]

    app.dependency_overrides[get_ai_provider] = lambda: provider

    try:
        first = await client.post(
            "/capture",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "message": "Paid ₹500",
            },
        )

        assert first.status_code == 200

        first_data = first.json()

        assert first_data["status"] == "needs_clarification"
        assert first_data["needs_clarification"] is True
        assert first_data["missing_fields"] == ["category"]

        conversation_id = first_data["conversation_id"]
        financial_event_id = first_data["financial_event_id"]

        second = await client.post(
            "/capture",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "conversation_id": conversation_id,
                "message": "Petrol",
            },
        )

        assert second.status_code == 200

        second_data = second.json()

        assert second_data["status"] == "completed"
        assert second_data["needs_clarification"] is False
        assert second_data["missing_fields"] == []

        assert second_data["conversation_id"] == conversation_id
        assert second_data["financial_event_id"] == financial_event_id

        assert provider.extract_financial_event.await_count == 2

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_capture_defaults_account_when_missing(client):
    token = await register_and_login(client)

    ai_response = CaptureAIResponse(
        status="completed",
        transactions=[
            AITransaction(
                type="expense",
                amount=2900,
                currency="INR",
                account=None,
                category="Bills",
                person=None,
                description="Supergrok AI subscription",
                transaction_date=None,
                direction="debit",
            )
        ],
        missing_fields=[],
        assistant_message="Recorded your ₹2900 subscription expense.",
        confidence=0.99,
    )

    provider = AsyncMock()
    provider.extract_financial_event.return_value = ai_response

    app.dependency_overrides[get_ai_provider] = lambda: provider

    try:
        response = await client.post(
            "/capture",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "message": "Bought Supergrok AI subscription for Rs.2900",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_capture_can_update_existing_transaction(client):
    token = await register_and_login(client)

    create_response = CaptureAIResponse(
        status="completed",
        transactions=[
            AITransaction(
                type="expense",
                amount=500,
                currency="INR",
                account="Spending Account",
                category="Transport",
                description="Petrol",
                direction="debit",
            )
        ],
        assistant_message="Recorded your petrol expense.",
        confidence=0.99,
    )
    update_response = CaptureAIResponse(
        status="completed",
        transactions=[
            AITransaction(
                operation="update",
                transaction_id=None,
                amount=650,
                description="Petrol for scooter",
            )
        ],
        assistant_message="Updated the transaction.",
        confidence=0.99,
    )

    provider = AsyncMock()
    responses = [create_response, update_response]
    provider.extract_financial_event.side_effect = responses
    app.dependency_overrides[get_ai_provider] = lambda: provider

    try:
        first = await client.post(
            "/capture",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Paid ₹500 for petrol"},
        )
        assert first.status_code == 200
        conversation_id = first.json()["conversation_id"]

        transactions = await client.get(
            "/transactions",
            headers={"Authorization": f"Bearer {token}"},
        )
        transaction_id = transactions.json()[0]["id"]
        responses[1].transactions[0].transaction_id = UUID(transaction_id)

        second = await client.post(
            "/capture",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "conversation_id": conversation_id,
                "message": "Actually it was ₹650 for scooter petrol",
            },
        )
        assert second.status_code == 200

        updated = await client.get(
            f"/transactions/{transaction_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert updated.status_code == 200
        assert updated.json()["amount"] == "650.00"
        assert updated.json()["description"] == "Petrol for scooter"

        messages = await client.get(
            f"/conversations/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert messages.status_code == 200
        assert messages.json()[-1]["role"] == "assistant"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_capture_can_delete_existing_transaction(client):
    token = await register_and_login(client)

    create_response = CaptureAIResponse(
        status="completed",
        transactions=[
            AITransaction(
                type="expense",
                amount=500,
                account="Spending Account",
                category="Transport",
                direction="debit",
            )
        ],
        assistant_message="Recorded the expense.",
        confidence=0.99,
    )
    delete_response = CaptureAIResponse(
        status="completed",
        transactions=[AITransaction(operation="delete")],
        assistant_message="Deleted the transaction.",
        confidence=0.99,
    )

    provider = AsyncMock()
    responses = [create_response, delete_response]
    provider.extract_financial_event.side_effect = responses
    app.dependency_overrides[get_ai_provider] = lambda: provider

    try:
        first = await client.post(
            "/capture",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Paid ₹500 for petrol"},
        )
        conversation_id = first.json()["conversation_id"]
        transactions = await client.get(
            "/transactions",
            headers={"Authorization": f"Bearer {token}"},
        )
        transaction_id = transactions.json()[0]["id"]
        responses[1].transactions[0].transaction_id = UUID(transaction_id)

        second = await client.post(
            "/capture",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "conversation_id": conversation_id,
                "message": "Delete that transaction",
            },
        )
        assert second.status_code == 200

        deleted = await client.get(
            f"/transactions/{transaction_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert deleted.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_capture_rejects_archived_conversation(client):
    token = await register_and_login(client)
    conversation = await client.post(
        "/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Archived"},
    )
    conversation_id = conversation.json()["id"]

    archived = await client.patch(
        f"/conversations/{conversation_id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert archived.status_code == 200

    response = await client.post(
        "/capture",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "conversation_id": conversation_id,
            "message": "Paid ₹500 for petrol",
        },
    )
    assert response.status_code == 404
