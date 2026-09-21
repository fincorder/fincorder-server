from uuid import UUID

from pydantic import BaseModel


class CaptureRequest(BaseModel):
    message: str
    conversation_id: UUID | None = None


class CaptureResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    assistant_message_id: UUID | None = None
    financial_event_id: UUID

    status: str
    assistant_message: str

    needs_clarification: bool
    missing_fields: list[str]