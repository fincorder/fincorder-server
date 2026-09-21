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
