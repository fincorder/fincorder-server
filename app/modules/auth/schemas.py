from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr | None = None
    status: str
    review_transactions: bool = True
    timezone: str = "UTC"
    avatar_url: str | None = None


class UpdateProfileRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    review_transactions: bool | None = None
    timezone: str | None = Field(default=None, max_length=64)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr | None = None
    status: str
    review_transactions: bool = True
    timezone: str = "UTC"
    avatar_url: str | None = None
    access_token: str
    token_type: str = "bearer"
