from uuid import UUID

from pydantic import BaseModel, Field


class CreateAccountRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    currency: str = Field(default="INR", min_length=3, max_length=3)


class UpdateAccountRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class AccountResponse(BaseModel):
    id: UUID
    name: str
    currency: str
    is_active: bool