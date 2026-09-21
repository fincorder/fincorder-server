from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AITransaction(BaseModel):
    operation: Literal["create", "update", "delete"] = "create"
    transaction_id: UUID | None = None

    type: Literal[
        "expense",
        "income",
        "transfer",
        "lend",
        "borrow",
        "repayment",
    ] | None = None

    amount: Decimal | None = None
    currency: str = "INR"

    account: str | None = None
    category: str | None = None
    person: str | None = None

    description: str | None = None
    transaction_date: str | None = None
    clear_fields: list[str] = Field(default_factory=list)

    direction: Literal["debit", "credit"] | None = None


class CaptureAIResponse(BaseModel):
    status: Literal["completed", "needs_clarification", "failed"]
    transactions: list[AITransaction] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    assistant_message: str
    confidence: float = Field(ge=0, le=1)
