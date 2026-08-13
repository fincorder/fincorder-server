from uuid import UUID

from pydantic import BaseModel


class CreatePersonRequest(BaseModel):
    name: str


class UpdatePersonRequest(BaseModel):
    name: str | None = None


class PersonResponse(BaseModel):
    id: UUID
    name: str