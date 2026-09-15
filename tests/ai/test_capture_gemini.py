from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.gemini_provider import GeminiProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.schemas import AITransaction, CaptureAIResponse
from app.core.config import settings
from app.modules.capture.dependencies import get_ai_provider


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


@pytest.fixture
def provider():
    with patch("app.ai.gemini_provider.genai.Client"):
        yield GeminiProvider()


@pytest.mark.asyncio
async def test_gemini_provider_returns_capture_response(provider, capture_response):
    mock_response = MagicMock()
    mock_response.parsed = capture_response
    mock_response.text = None

    with patch.object(
        provider.client.aio.models,
        "generate_content",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_generate:

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

    mock_generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_gemini_provider_handles_clarification(provider):
    capture_response = CaptureAIResponse(
        status="needs_clarification",
        transactions=[],
        missing_fields=["category"],
        assistant_message="What was the ₹500 for?",
        confidence=0.88,
    )

    mock_response = MagicMock()
    mock_response.parsed = capture_response
    mock_response.text = None

    with patch.object(
        provider.client.aio.models,
        "generate_content",
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
async def test_gemini_provider_passes_context(provider, capture_response):
    mock_response = MagicMock()
    mock_response.parsed = capture_response
    mock_response.text = None

    context = {
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
        provider.client.aio.models,
        "generate_content",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_generate:

        result = await provider.extract_financial_event(
            message="Paid ₹500 for petrol",
            context=context,
        )

    assert result == capture_response

    call_kwargs = mock_generate.call_args.kwargs

    assert call_kwargs["model"] == provider.model
    assert call_kwargs["config"].system_instruction
    assert call_kwargs["config"].response_json_schema == CaptureAIResponse.model_json_schema()

    contents = call_kwargs["contents"]

    assert contents[0]["role"] == "user"
    assert "2026-08-31" in contents[0]["parts"][0]["text"]
    assert "Salary Account" in contents[0]["parts"][0]["text"]
    assert "Fouzan" in contents[0]["parts"][0]["text"]
    assert "Paid ₹300 for dinner" in contents[0]["parts"][0]["text"]
    assert "Recorded your ₹300 dinner expense." in contents[0]["parts"][0]["text"]


@pytest.mark.asyncio
async def test_gemini_provider_without_context(provider, capture_response):
    mock_response = MagicMock()
    mock_response.parsed = capture_response
    mock_response.text = None

    with patch.object(
        provider.client.aio.models,
        "generate_content",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_generate:

        await provider.extract_financial_event(
            message="Paid ₹500 for petrol"
        )

    contents = mock_generate.call_args.kwargs["contents"]

    assert contents[-1] == {
        "role": "user",
        "parts": [{"text": "Paid ₹500 for petrol"}],
    }


@pytest.mark.asyncio
async def test_gemini_provider_parses_text_when_parsed_missing(provider):
    capture_response = CaptureAIResponse(
        status="completed",
        transactions=[],
        missing_fields=[],
        assistant_message="Recorded.",
        confidence=0.95,
    )

    mock_response = MagicMock()
    mock_response.parsed = None
    mock_response.text = capture_response.model_dump_json()

    with patch.object(
        provider.client.aio.models,
        "generate_content",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):

        result = await provider.extract_financial_event(
            message="Paid ₹500 for petrol"
        )

    assert result == capture_response


@pytest.mark.asyncio
async def test_gemini_provider_returns_failed_when_output_missing(provider):
    mock_response = MagicMock()
    mock_response.parsed = None
    mock_response.text = ""

    with patch.object(
        provider.client.aio.models,
        "generate_content",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):

        result = await provider.extract_financial_event(
            message="Paid ₹500 for petrol"
        )

    assert result.status == "failed"
    assert result.transactions == []
    assert result.missing_fields == []


def test_get_ai_provider_returns_gemini(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")

    with patch("app.ai.gemini_provider.genai.Client"):
        provider = get_ai_provider()

    assert isinstance(provider, GeminiProvider)


def test_get_ai_provider_returns_openai(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")

    provider = get_ai_provider()

    assert isinstance(provider, OpenAIProvider)
