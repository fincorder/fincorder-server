from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.ai.schemas import AITransaction, CaptureAIResponse
from app.main import app
from app.modules.capture.dependencies import get_ai_provider


async def register_and_login(client):
    await client.post(
        "/auth/register",
        json={"name": "Aashir", "email": "aashir@example.com", "password": "password123"},
    )
    login = await client.post(
        "/auth/login",
        json={"email": "aashir@example.com", "password": "password123"},
    )
    return login.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def expense(amount, **kwargs):
    return AITransaction(
        type="expense",
        amount=amount,
        currency="INR",
        direction="debit",
        **kwargs,
    )


async def post_capture(client, token, message, conversation_id=None):
    payload = {"message": message}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    return await client.post("/capture", headers=auth(token), json=payload)


async def confirm(client, token, data):
    return await client.post(
        f"/capture/{data['financial_event_id']}/confirm",
        headers=auth(token),
        json={"transactions": data["proposed_transactions"], "revision": data["revision"]},
    )


@pytest.mark.asyncio
async def test_capture_returns_persisted_proposal_without_mutating_transactions(client):
    token = await register_and_login(client)
    provider = AsyncMock()
    provider.extract_financial_event.return_value = CaptureAIResponse(
        status="completed",
        transactions=[expense(500, account="Spending Account", category="Transport", description="Petrol")],
        assistant_message="Recorded the expense.",
        confidence=0.99,
    )
    app.dependency_overrides[get_ai_provider] = lambda: provider

    try:
        response = await post_capture(client, token, "Paid 500 for petrol")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "awaiting_confirmation"
        assert data["awaiting_confirmation"] is True
        assert data["proposed_transactions"][0]["amount"] == "500"

        transactions = await client.get("/transactions", headers=auth(token))
        assert transactions.json() == []

        events = await client.get(
            f"/financial-events/conversation/{data['conversation_id']}",
            headers=auth(token),
        )
        assert events.status_code == 200
        assert events.json()[0]["status"] == "awaiting_confirmation"
        assert events.json()[0]["extracted_data"]["transactions"][0]["amount"] == "500"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_confirming_proposal_creates_transaction(client):
    token = await register_and_login(client)
    provider = AsyncMock()
    provider.extract_financial_event.return_value = CaptureAIResponse(
        status="completed",
        transactions=[expense(500, account="Spending Account", category="Transport")],
        assistant_message="Ready.",
        confidence=0.99,
    )
    app.dependency_overrides[get_ai_provider] = lambda: provider

    try:
        data = (await post_capture(client, token, "Paid 500 for petrol")).json()
        response = await confirm(client, token, data)
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert len(response.json()["transaction_ids"]) == 1

        transactions = await client.get("/transactions", headers=auth(token))
        assert len(transactions.json()) == 1
        assert transactions.json()[0]["amount"] == "500.00"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_clarification_keeps_amount_locked_until_confirmation(client):
    token = await register_and_login(client)
    provider = AsyncMock()
    provider.extract_financial_event.side_effect = [
        CaptureAIResponse(
            status="needs_clarification",
            transactions=[],
            missing_fields=["category"],
            assistant_message="What was the 219 for?",
            confidence=0.9,
        ),
        CaptureAIResponse(
            status="needs_clarification",
            transactions=[expense(500, category="Bills")],
            missing_fields=["account"],
            assistant_message="Which account was used for 500?",
            confidence=0.9,
        ),
        CaptureAIResponse(
            status="completed",
            transactions=[expense(500, account="Spending Account", category="Bills", description="Airtel recharge")],
            assistant_message="Recorded 500.",
            confidence=0.9,
        ),
    ]
    app.dependency_overrides[get_ai_provider] = lambda: provider

    try:
        first = (await post_capture(client, token, "Spent 219 rs")).json()
        second = (await post_capture(client, token, "Airtel recharge", first["conversation_id"])).json()
        assert "219" in second["assistant_message"]
        third = (await post_capture(client, token, "The SBI account", first["conversation_id"])).json()
        assert third["status"] == "awaiting_confirmation"
        assert third["proposed_transactions"][0]["amount"] == "219"

        confirmed = await confirm(client, token, third)
        assert confirmed.status_code == 200
        transactions = await client.get("/transactions", headers=auth(token))
        assert transactions.json()[0]["amount"] == "219.00"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_is_only_applied_after_confirmation(client):
    token = await register_and_login(client)
    provider = AsyncMock()
    create = CaptureAIResponse(
        status="completed",
        transactions=[expense(500, account="Spending Account", category="Transport", description="Petrol")],
        assistant_message="Ready.",
        confidence=0.99,
    )
    update = CaptureAIResponse(
        status="completed",
        transactions=[AITransaction(operation="update", amount=650, description="Scooter petrol")],
        assistant_message="Updated.",
        confidence=0.99,
    )
    provider.extract_financial_event.side_effect = [create, update]
    app.dependency_overrides[get_ai_provider] = lambda: provider

    try:
        created = (await post_capture(client, token, "Paid 500 for petrol")).json()
        await confirm(client, token, created)
        transaction = (await client.get("/transactions", headers=auth(token))).json()[0]
        update.transactions[0].transaction_id = UUID(transaction["id"])

        proposal = (await post_capture(client, token, "Actually it was 650 for scooter petrol", created["conversation_id"])).json()
        assert proposal["status"] == "awaiting_confirmation"
        unchanged = (await client.get(f"/transactions/{transaction['id']}", headers=auth(token))).json()
        assert unchanged["amount"] == "500.00"

        confirmed = await confirm(client, token, proposal)
        assert confirmed.status_code == 200
        changed = (await client.get(f"/transactions/{transaction['id']}", headers=auth(token))).json()
        assert changed["amount"] == "650.00"
        assert changed["description"] == "Scooter petrol"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_is_only_applied_after_confirmation(client):
    token = await register_and_login(client)
    provider = AsyncMock()
    delete_response = CaptureAIResponse(
        status="completed",
        transactions=[AITransaction(operation="delete")],
        assistant_message="Ready to remove it.",
        confidence=0.99,
    )
    provider.extract_financial_event.side_effect = [
        CaptureAIResponse(status="completed", transactions=[expense(500, category="Transport")], assistant_message="Ready.", confidence=0.99),
        delete_response,
    ]
    app.dependency_overrides[get_ai_provider] = lambda: provider

    try:
        created = (await post_capture(client, token, "Paid 500 for petrol")).json()
        await confirm(client, token, created)
        transaction_id = (await client.get("/transactions", headers=auth(token))).json()[0]["id"]
        delete_response.transactions[0].transaction_id = UUID(transaction_id)
        proposal = (await post_capture(client, token, "Delete that transaction", created["conversation_id"])).json()
        assert (await client.get(f"/transactions/{transaction_id}", headers=auth(token))).status_code == 200
        assert (await confirm(client, token, proposal)).status_code == 200
        assert (await client.get(f"/transactions/{transaction_id}", headers=auth(token))).status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_explicit_correction_returns_update_proposal(client):
    token = await register_and_login(client)
    provider = AsyncMock()
    provider.extract_financial_event.side_effect = [
        CaptureAIResponse(status="completed", transactions=[expense(500, category="Bills")], assistant_message="Ready.", confidence=0.99),
        CaptureAIResponse(status="needs_clarification", transactions=[], missing_fields=["category"], assistant_message="What was 219 for?", confidence=0.9),
    ]
    app.dependency_overrides[get_ai_provider] = lambda: provider

    try:
        created = (await post_capture(client, token, "Spent 500 on Airtel recharge")).json()
        await confirm(client, token, created)
        transaction_id = (await client.get("/transactions", headers=auth(token))).json()[0]["id"]
        corrected = (await post_capture(client, token, "Not 500, I spent 219 rs only", created["conversation_id"])).json()
        assert corrected["status"] == "awaiting_confirmation"
        assert corrected["proposed_transactions"][0]["operation"] == "update"
        assert corrected["proposed_transactions"][0]["transaction_id"] == transaction_id
        assert corrected["proposed_transactions"][0]["amount"] == "219"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_capture_uses_default_account_and_today_when_unspecified(client):
    token = await register_and_login(client)
    provider = AsyncMock()
    provider.extract_financial_event.return_value = CaptureAIResponse(
        status="completed",
        transactions=[expense(200, account=None, category="Food", transaction_date=None)],
        assistant_message="Ready.",
        confidence=0.99,
    )
    app.dependency_overrides[get_ai_provider] = lambda: provider

    try:
        data = (await post_capture(client, token, "Spent 200 on coffee")).json()
        proposal = data["proposed_transactions"][0]
        assert proposal["account"] == "Spending Account"
        assert proposal["transaction_date"] == datetime.now(timezone.utc).date().isoformat()
    finally:
        app.dependency_overrides.clear()
