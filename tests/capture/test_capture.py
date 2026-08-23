from unittest.mock import AsyncMock, patch

import pytest

from app.ai.schemas import AITransaction, CaptureAIResponse


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

    with patch(
        "app.modules.capture.service.get_ai_provider"
    ) as mock_provider:
        provider = AsyncMock()
        provider.extract_financial_event.return_value = ai_response
        mock_provider.return_value = provider

        response = await client.post(
            "/capture",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Paid ₹500 for petrol"},
        )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "completed"
    assert data["needs_clarification"] is False
    assert data["assistant_message"] == "Recorded your ₹500 petrol expense."
    assert data["missing_fields"] == []


@pytest.mark.asyncio
async def test_capture_needs_clarification(client):
    token = await register_and_login(client)

    ai_response = CaptureAIResponse(
        status="needs_clarification",
        transactions=[],
        missing_fields=["category"],
        assistant_message="What was the ₹500 for?",
        confidence=0.88,
    )

    with patch(
        "app.modules.capture.service.get_ai_provider"
    ) as mock_provider:
        provider = AsyncMock()
        provider.extract_financial_event.return_value = ai_response
        mock_provider.return_value = provider

        response = await client.post(
            "/capture",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Paid ₹500"},
        )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "needs_clarification"
    assert data["needs_clarification"] is True
    assert data["missing_fields"] == ["category"]
    assert data["assistant_message"] == "What was the ₹500 for?"


@pytest.mark.asyncio
async def test_capture_requires_auth(client):
    response = await client.post(
        "/capture",
        json={"message": "Paid ₹500 for petrol"},
    )

    assert response.status_code == 401