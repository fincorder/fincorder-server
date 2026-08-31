from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.openai_provider import OpenAIProvider
from app.ai.schemas import AITransaction, CaptureAIResponse


@pytest.fixture
def capture_response():
    return CaptureAIResponse(
        status="completed",
        transactions=[
            AITransaction(
                type="expense",
                amount=Decimal("500"),
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


@pytest.mark.asyncio
async def test_openai_provider_returns_capture_response(capture_response):
    provider = OpenAIProvider()

    mock_response = MagicMock()
    mock_response.output_parsed = capture_response

    with patch.object(
        provider.client.responses,
        "parse",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_parse:

        result = await provider.extract_financial_event(
            message="Paid ₹500 for petrol"
        )

    assert isinstance(result, CaptureAIResponse)
    assert result.status == "completed"
    assert len(result.transactions) == 1

    transaction = result.transactions[0]

    assert transaction.type == "expense"
    assert transaction.amount == Decimal("500")
    assert transaction.currency == "INR"
    assert transaction.account == "Spending Account"
    assert transaction.category == "Transport"
    assert transaction.description == "Petrol"
    assert transaction.direction == "debit"

    mock_parse.assert_awaited_once()


@pytest.mark.asyncio
async def test_openai_provider_handles_clarification():
    provider = OpenAIProvider()

    capture_response = CaptureAIResponse(
        status="needs_clarification",
        transactions=[],
        missing_fields=["category"],
        assistant_message="What was the ₹500 for?",
        confidence=0.88,
    )

    mock_response = MagicMock()
    mock_response.output_parsed = capture_response

    with patch.object(
        provider.client.responses,
        "parse",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):

        result = await provider.extract_financial_event(
            message="Paid ₹500"
        )

    assert result.status == "needs_clarification"
    assert result.transactions == []
    assert result.missing_fields == ["category"]
    assert result.assistant_message == "What was the ₹500 for?"
    assert result.confidence == 0.88


@pytest.mark.asyncio
async def test_openai_provider_passes_context():
    provider = OpenAIProvider()

    capture_response = CaptureAIResponse(
        status="completed",
        transactions=[],
        missing_fields=[],
        assistant_message="Recorded.",
        confidence=0.95,
    )

    mock_response = MagicMock()
    mock_response.output_parsed = capture_response

    context = context = {
        "today": "2026-08-31",
        "accounts": ["Salary Account", "Spending Account", "Cash"],
        "categories": ["Transport", "Food"],
        "people": ["Fouzan", "Ahmed"],
        "messages": [
            {
                "role": "user",
                "content": "Paid ₹300 for dinner",
            },
            {
                "role": "assistant",
                "content": "Recorded your ₹300 dinner expense.",
            },
        ],
    }

    with patch.object(
        provider.client.responses,
        "parse",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_parse:

        result = await provider.extract_financial_event(
            message="Paid ₹500 for petrol",
            context=context,
        )

    assert result == capture_response

    call_kwargs = mock_parse.call_args.kwargs

    assert call_kwargs["model"] == provider.model
    assert call_kwargs["instructions"]
    assert call_kwargs["text_format"] is CaptureAIResponse

    input_messages = call_kwargs["input"]

    assert input_messages[0]["role"] == "developer"
    assert "2026-08-31" in input_messages[0]["content"]
    assert "Salary Account" in input_messages[0]["content"]
    assert "Fouzan" in input_messages[0]["content"]
    assert "Paid ₹300 for dinner" in input_messages[0]["content"]
    assert "Recorded your ₹300 dinner expense." in input_messages[0]["content"]


@pytest.mark.asyncio
async def test_openai_provider_without_context():
    provider = OpenAIProvider()

    capture_response = CaptureAIResponse(
        status="completed",
        transactions=[],
        missing_fields=[],
        assistant_message="Recorded.",
        confidence=0.95,
    )

    mock_response = MagicMock()
    mock_response.output_parsed = capture_response

    with patch.object(
        provider.client.responses,
        "parse",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_parse:

        await provider.extract_financial_event(
            message="Paid ₹500 for petrol"
        )

    input_messages = mock_parse.call_args.kwargs["input"]

    assert input_messages[-1] == {
        "role": "user",
        "content": "Paid ₹500 for petrol",
    }