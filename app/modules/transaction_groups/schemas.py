from uuid import UUID

from pydantic import BaseModel


class TransactionGroupResponse(BaseModel):
    id: UUID
    financial_event_id: UUID
    status: str