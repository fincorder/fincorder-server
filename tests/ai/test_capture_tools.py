from types import SimpleNamespace
from unittest.mock import AsyncMock
import json

import pytest

from app.ai.openai_provider import OpenAIProvider
from app.ai.schemas import AITransaction, CaptureAIResponse


def tool_call(name, arguments):
    return SimpleNamespace(status="completed", output=[SimpleNamespace(type="function_call", name=name, arguments=json.dumps(arguments), call_id="call_1")])


@pytest.mark.asyncio
@pytest.mark.parametrize("review, action", [(True, "propose_transactions"), (False, "apply_transactions")])
async def test_tool_search_then_validated_batch(review, action):
    result = CaptureAIResponse(status="completed", transactions=[AITransaction(type="expense", direction="debit", amount=219)], assistant_message="Ready", confidence=.99)
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.model = "gpt-4.1"
    create = AsyncMock(side_effect=[tool_call("search_transactions", {"search": "Airtel", "date_from": None, "date_to": None}), tool_call(action, result.model_dump(mode="json"))])
    provider.client = SimpleNamespace(responses=SimpleNamespace(create=create))
    search = AsyncMock(return_value=[{"id": "owned-id", "description": "Airtel"}])
    context = {"today": "2026-09-22", "accounts": [], "categories": [], "people": [], "messages": [], "review_transactions": review}
    response = await provider.extract_financial_event("Airtel was 219", context, search_tool=search)
    assert response.transactions[0].amount == 219
    search.assert_awaited_once()
    kwargs = create.call_args.kwargs
    assert kwargs["tools"][0]["name"] == action
    assert kwargs["tools"][0]["strict"] is True
    assert kwargs["parallel_tool_calls"] is False
    assert any(isinstance(item, dict) and item.get("type") == "function_call_output" and "owned-id" in item["output"] for item in kwargs["input"])


@pytest.mark.asyncio
async def test_incomplete_tool_response_stops_without_actions():
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.model = "gpt-4.1"
    create = AsyncMock(return_value=SimpleNamespace(status="incomplete", output=[]))
    provider.client = SimpleNamespace(responses=SimpleNamespace(create=create))
    response = await provider.extract_financial_event("hi", {"today": "2026-09-22", "accounts": [], "categories": [], "people": [], "messages": []})
    assert response.status == "failed"
    assert create.await_count == 4
