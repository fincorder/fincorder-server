from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, WithJsonSchema


class AITransaction(BaseModel):
    draft_id: str | None = None
    changed_fields: list[str] = Field(default_factory=list)
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

    # Advertise a JSON number to AI providers, while retaining Decimal validation
    # and storage. Pydantic's default Decimal string regex breaks GPT-4.1 output.
    amount: Annotated[Decimal, WithJsonSchema({"type": "number"}, mode="validation")] | None = None
    currency: str | None = None

    account: str | None = None
    category: str | None = None
    person: str | None = None

    description: str | None = None
    transaction_date: str | None = None
    clear_fields: list[str] = Field(default_factory=list)

    direction: Literal["debit", "credit"] | None = None


class CaptureAIResponse(BaseModel):
    continuation_event_id: UUID | None = None
    status: Literal["completed", "needs_clarification", "failed"]
    transactions: list[AITransaction] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    assistant_message: str
    confidence: float = Field(ge=0, le=1)
