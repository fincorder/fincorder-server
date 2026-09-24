import os
from datetime import datetime
from decimal import Decimal

import pytest

from app.ai.openai_provider import OpenAIProvider
from app.main import app
from app.modules.capture.dependencies import get_ai_provider


@pytest.mark.skipif(os.getenv("FINCORDER_LIVE_AI") != "1", reason="Requires a live OpenAI request")
@pytest.mark.asyncio
@pytest.mark.parametrize("item, day", [("snacks", "today"), ("icecream", "yesterday")])
async def test_live_capture_creates_and_updates_transaction(client, item, day):
    registration = await client.post("/auth/register", json={
        "name": "Capture test", "email": "capture-live@example.com", "password": "password123",
    })
    assert registration.status_code == 201
    login = await client.post("/auth/login", json={
        "email": "capture-live@example.com", "password": "password123",
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    await client.patch("/auth/me", headers=headers, json={"review_transactions": False})

    provider = OpenAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        async with provider.client:
            response = await client.post("/capture", headers=headers, json={
                "message": f"Bought {item} for Rs.20 {day}",
            })
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "completed", response.text
            history = await client.get("/transactions", headers=headers)
            assert history.status_code == 200
            transactions = history.json()
            assert len(transactions) == 1
            original = transactions[0]
            assert Decimal(original["amount"]) == Decimal("20")
            assert original["type"] == "expense"
            assert original["direction"] == "debit"
            assert original["currency"] == "INR"

            correction = await client.post("/capture", headers=headers, json={
                "conversation_id": response.json()["conversation_id"],
                "message": f"Actually I spent 40rs in the {item} not 20.",
            })
            assert correction.status_code == 200, correction.text
            assert correction.json()["status"] == "completed", correction.text
            updated_history = await client.get("/transactions", headers=headers)
            assert updated_history.status_code == 200
            assert len(updated_history.json()) == 1
            updated = updated_history.json()[0]
            assert updated["id"] == original["id"]
            assert Decimal(updated["amount"]) == Decimal("40")
            assert datetime.fromisoformat(updated["transaction_date"]) == datetime.fromisoformat(original["transaction_date"])
            for field in ("account_id", "category_id", "person_id", "type", "direction", "currency", "description"):
                assert updated[field] == original[field]
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)


@pytest.mark.skipif(os.getenv("FINCORDER_LIVE_AI") != "1", reason="Requires a live OpenAI request")
@pytest.mark.asyncio
async def test_live_multiturn_lending_and_cash(client):
    from tests.capture.test_capture import register_and_login, auth, post_capture
    token = await register_and_login(client)
    await client.patch('/auth/me', headers=auth(token), json={"review_transactions": False})
    await client.post('/people', headers=auth(token), json={"name": "Farooq"})
    provider = OpenAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        async with provider.client:
            first = await post_capture(client, token, "Lent 350")
            assert first.status_code == 200, first.text
            assert first.json()["status"] == "needs_clarification", first.text
            conversation = first.json()["conversation_id"]
            second = await post_capture(client, token, "Farooq", conversation)
            assert second.json()["status"] == "completed", second.text
            third = await post_capture(client, token, "Spent 750 today by cash", conversation)
            assert third.json()["status"] == "needs_clarification", third.text
            fourth = await post_capture(client, token, "Wifi recharge", conversation)
            assert fourth.json()["status"] == "completed", fourth.text
            transactions = (await client.get('/transactions', headers=auth(token))).json()
            assert len(transactions) == 2
            lend = next(t for t in transactions if t["type"] == "lend")
            assert Decimal(lend["amount"]) == 350
            expense = next(t for t in transactions if t["type"] == "expense")
            assert Decimal(expense["amount"]) == 750
            accounts = (await client.get('/accounts', headers=auth(token))).json()
            assert expense["account_id"] == next(a["id"] for a in accounts if a["name"] == "Cash")
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
