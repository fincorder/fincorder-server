from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class AITransaction(BaseModel):
    type: Literal[
        "expense",
        "income",
        "transfer",
        "lend",
        "borrow",
        "repayment",
    ]

    amount: Decimal = Field(gt=0)
    currency: str = "INR"

    account: str | None = None
    category: str | None = None
    person: str | None = None

    description: str | None = None
    transaction_date: str | None = None

    direction: Literal["debit", "credit"] | None = None


class CaptureAIResponse(BaseModel):
    status: Literal["completed", "needs_clarification", "failed"]
    transactions: list[AITransaction] = []
    missing_fields: list[str] = []
    assistant_message: str
    confidence: float = Field(ge=0, le=1)