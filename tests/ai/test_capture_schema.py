from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.ai.schemas import AITransaction, CaptureAIResponse


def test_amount_generation_schema_uses_number_without_decimal_regex():
    schema = CaptureAIResponse.model_json_schema()
    amount = schema["$defs"]["AITransaction"]["properties"]["amount"]
    assert amount["anyOf"] == [{"type": "number"}, {"type": "null"}]


@pytest.mark.parametrize("value", ["20", "20.10", "123456789012345.67"])
def test_json_amount_still_parses_as_exact_decimal(value):
    transaction = AITransaction.model_validate_json('{"amount": ' + value + '}')
    assert isinstance(transaction.amount, Decimal)
    assert transaction.amount == Decimal(value)


def test_amount_schema_override_does_not_disable_validation():
    with pytest.raises(ValidationError):
        AITransaction(amount="not an amount")


def test_amount_can_be_omitted_for_conversation_edits():
    assert AITransaction(operation="delete").amount is None
