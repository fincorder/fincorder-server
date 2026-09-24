from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


REPORTS = frozenset({
    "overview", "spending", "income", "categories", "accounts", "people",
    "activity", "transfers", "types", "quality", "pivot",
})
DIMENSIONS = frozenset({"month", "category", "account", "person", "type"})
MEASURES = frozenset({"amount", "count", "debit", "credit", "average"})


@dataclass(frozen=True)
class ReportFilters:
    date_from: date | None = None
    date_to: date | None = None
    currency: str = "INR"
    account_id: UUID | None = None
    category_id: UUID | None = None
    person_id: UUID | None = None
    transaction_type: str | None = None
    direction: str | None = None
    search: str | None = None
    granularity: str = "month"
    sort_by: str = "amount"
    sort_order: str = "desc"
    limit: int = 25
    offset: int = 0
    pivot_row: str = "category"
    pivot_column: str = "month"
    pivot_measure: str = "amount"

    def validate(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be before or equal to date_to")
        if self.pivot_row not in DIMENSIONS or self.pivot_column not in DIMENSIONS:
            raise ValueError("Invalid pivot dimension")
        if self.pivot_row == self.pivot_column:
            raise ValueError("Pivot row and column must differ")
        if self.pivot_measure not in MEASURES:
            raise ValueError("Invalid pivot measure")


def timezone_for(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def date_bounds(filters: ReportFilters, timezone_name: str | None) -> tuple[datetime | None, datetime | None]:
    zone = timezone_for(timezone_name)
    start = datetime.combine(filters.date_from, time.min, zone).astimezone(timezone.utc) if filters.date_from else None
    end = datetime.combine(filters.date_to + timedelta(days=1), time.min, zone).astimezone(timezone.utc) if filters.date_to else None
    return start, end
