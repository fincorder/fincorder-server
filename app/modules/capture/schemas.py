from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.ai.schemas import AITransaction


class CaptureRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000, pattern=r"\S")
    conversation_id: UUID | None = None
    request_id: UUID = Field(default_factory=uuid4)
    financial_event_id: UUID | None = None


class CaptureResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    assistant_message_id: UUID | None = None
    financial_event_id: UUID

    status: str
    assistant_message: str

    needs_clarification: bool
    missing_fields: list[str]
    awaiting_confirmation: bool = False
    proposed_transactions: list[AITransaction] = Field(default_factory=list)
    transaction_ids: list[UUID] = Field(default_factory=list)
    revision: int = 1


class ConfirmCaptureRequest(BaseModel):
    transactions: list[AITransaction] = Field(min_length=1, max_length=30)
    revision: int = Field(default=1, ge=1)


class ConfirmCaptureResponse(BaseModel):
    financial_event_id: UUID
    status: str
    assistant_message: str
    transaction_ids: list[UUID] = Field(default_factory=list)
    revision: int = 1
