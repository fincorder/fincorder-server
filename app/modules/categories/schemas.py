from uuid import UUID

from typing import Literal
from pydantic import BaseModel


class CreateCategoryRequest(BaseModel):
    name: str
    type: Literal["expense", "income"]


class UpdateCategoryRequest(BaseModel):
    name: str | None = None


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    type: str