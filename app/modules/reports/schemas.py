from typing import Any

from pydantic import BaseModel


class ReportResponse(BaseModel):
    report: str
    currency: str
    date_from: str | None
    date_to: str | None
    metrics: dict[str, Any]
    comparison: dict[str, Any] | None
    trend: list[dict[str, Any]]
    breakdowns: dict[str, list[dict[str, Any]]]
    rows: list[dict[str, Any]]
    pivot_columns: list[str]
    total: int
    limit: int
    offset: int
    has_next: bool


class ReportOption(BaseModel):
    id: str
    name: str
    currency: str | None = None


class ReportOptionsResponse(BaseModel):
    accounts: list[ReportOption]
    categories: list[ReportOption]
    people: list[ReportOption]
    currencies: list[str]
