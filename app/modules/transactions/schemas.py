from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateTransactionRequest(BaseModel):
    transaction_group_id: UUID
    account_id: UUID
    category_id: UUID | None = None
    person_id: UUID | None = None
    type: Literal[
        "expense",
        "income",
        "transfer",
        "lend",
        "borrow",
        "repayment",
    ]
    direction: Literal["debit", "credit"]
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    description: str | None = None
    transaction_date: datetime


class UpdateTransactionRequest(BaseModel):
    account_id: UUID | None = None
    category_id: UUID | None = None
    person_id: UUID | None = None
    type: Literal[
        "expense",
        "income",
        "transfer",
        "lend",
        "borrow",
        "repayment",
    ] | None = None
    direction: Literal["debit", "credit"] | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    description: str | None = None
    transaction_date: datetime | None = None


class TransactionResponse(BaseModel):
    id: UUID
    transaction_group_id: UUID
    account_id: UUID
    category_id: UUID | None
    person_id: UUID | None
    type: str
    direction: str
    amount: Decimal
    currency: str
    description: str | None
    transaction_date: datetime
