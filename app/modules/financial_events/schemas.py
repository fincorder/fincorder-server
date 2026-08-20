from uuid import UUID

from pydantic import BaseModel


class FinancialEventResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    source_message_id: UUID
    status: str
    raw_text: str
    extracted_data: dict | None
    missing_fields: list | None
    error: str | None