from uuid import UUID

from pydantic import BaseModel, Field


class CreateAccountRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    is_default: bool = False


class UpdateAccountRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_default: bool | None = None


class AccountResponse(BaseModel):
    id: UUID
    name: str
    currency: str
    is_active: bool
    is_default: bool
