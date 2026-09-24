from datetime import datetime
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
    assistant_message_id: UUID | None = None
    revision: int = 1


class FinancialEventReviewResponse(FinancialEventResponse):
    conversation_title: str | None = None
    created_at: datetime
    updated_at: datetime


class FinancialEventReviewPageResponse(BaseModel):
    items: list[FinancialEventReviewResponse]
    total: int
    limit: int
    offset: int
    has_next: bool
