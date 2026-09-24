from dataclasses import replace
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.reports.export import report_csv
from app.modules.reports.filters import ReportFilters
from app.modules.reports.schemas import ReportOptionsResponse, ReportResponse
from app.modules.reports.service import build_report
from app.modules.reports.repository import report_options
from app.modules.users.models import User


router = APIRouter(prefix="/reports", tags=["Reports"])
ReportName = Literal["overview", "spending", "income", "categories", "accounts", "people", "activity", "transfers", "types", "quality", "pivot"]


@router.get("/options", response_model=ReportOptionsResponse)
async def get_report_options_controller(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await report_options(db, current_user.id)


def report_filters(
    date_from: date | None = None,
    date_to: date | None = None,
    currency: str = Query(default="INR", pattern=r"^[A-Za-z]{3}$"),
    account_id: UUID | None = None,
    category_id: UUID | None = None,
    person_id: UUID | None = None,
    type: Literal["expense", "income", "transfer", "lend", "borrow", "repayment"] | None = None,
    direction: Literal["debit", "credit"] | None = None,
    search: str | None = Query(default=None, max_length=100),
    granularity: Literal["day", "week", "month"] = "month",
    sort_by: str = Query(default="amount", max_length=30),
    sort_order: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    pivot_row: Literal["month", "category", "account", "person", "type"] = "category",
    pivot_column: Literal["month", "category", "account", "person", "type"] = "month",
    pivot_measure: Literal["amount", "count", "debit", "credit", "average"] = "amount",
) -> ReportFilters:
    return ReportFilters(
        date_from=date_from, date_to=date_to, currency=currency.upper(), account_id=account_id,
        category_id=category_id, person_id=person_id, transaction_type=type, direction=direction,
        search=search, granularity=granularity, sort_by=sort_by, sort_order=sort_order,
        limit=limit, offset=offset, pivot_row=pivot_row, pivot_column=pivot_column, pivot_measure=pivot_measure,
    )


@router.get("/export")
async def export_report_controller(
    view: ReportName,
    filters: ReportFilters = Depends(report_filters),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await build_report(db, current_user, view, replace(filters, offset=0, limit=10**9))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=report_csv(data),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="fincorder-{view}.csv"'},
    )


@router.get("/{view}", response_model=ReportResponse)
async def get_report_controller(
    view: ReportName,
    filters: ReportFilters = Depends(report_filters),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await build_report(db, current_user, view, filters)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
