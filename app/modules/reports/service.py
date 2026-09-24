from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.aggregation import (
    base_metrics, people_rows, pivot_rows, quality_rows, summary_rows,
    transaction_row, transfer_rows, trend_rows,
)
from app.modules.reports.filters import REPORTS, ReportFilters
from app.modules.reports.repository import capture_quality_counts, load_facts
from app.modules.users.models import User


def _json(value):
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal("0.01")))
    if isinstance(value, (date, UUID)):
        return value.isoformat() if isinstance(value, date) else str(value)
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json(item) for item in value]
    return value


def _sort_rows(rows: list[dict], filters: ReportFilters) -> list[dict]:
    allowed = {"amount", "count", "spending", "income", "debit", "credit", "label", "transaction_date", "owed_to_you", "you_owe", "net_position", "total"}
    fallback = "owed_to_you" if rows and "owed_to_you" in rows[0] else "transaction_date" if rows and "transaction_date" in rows[0] else "amount"
    key = filters.sort_by if filters.sort_by in allowed and any(filters.sort_by in row for row in rows) else fallback
    if rows and key not in rows[0]:
        key = "label" if "label" in rows[0] else next(iter(rows[0]))
    return sorted(rows, key=lambda row: (row.get(key) is not None, row.get(key) or 0), reverse=filters.sort_order == "desc")


async def build_report(db: AsyncSession, user: User, report: str, filters: ReportFilters) -> dict:
    if report not in REPORTS:
        raise ValueError("Unknown report")
    filters.validate()
    facts = await load_facts(db, user.id, filters, user.timezone)
    transfer_facts = await load_facts(db, user.id, filters, user.timezone, transfers=True)
    transfers = transfer_rows(transfer_facts, filters.account_id, filters.search)
    if filters.category_id or filters.person_id or (filters.transaction_type and filters.transaction_type != "transfer") or filters.direction:
        transfers = []
    if filters.transaction_type == "transfer":
        facts = []
    metrics = base_metrics(facts, transfers)
    comparison = None
    if filters.date_from and filters.date_to and report in {"overview", "spending", "income", "categories"}:
        days = (filters.date_to - filters.date_from).days + 1
        prior_to = filters.date_from - timedelta(days=1)
        prior_from = filters.date_from - timedelta(days=days)
        prior_facts = await load_facts(db, user.id, replace(filters, date_from=prior_from, date_to=prior_to), user.timezone)
        prior_metrics = base_metrics(prior_facts, [])
        comparison = {"date_from": prior_from, "date_to": prior_to, "spending": prior_metrics["spending"], "income": prior_metrics["income"]}
        metrics["spending_change"] = metrics["spending"] - prior_metrics["spending"]
        metrics["income_change"] = metrics["income"] - prior_metrics["income"]
        previous_category_rows = summary_rows(prior_facts, "category", spending_only=True)
        previous_categories = {row["key"]: row for row in previous_category_rows}
    trend = trend_rows(facts, transfers, filters.granularity, user.timezone)
    category_facts = facts
    if report == "income":
        category_facts = [fact for fact in facts if fact.type == "income" and fact.direction == "credit"]
    breakdowns = {
        "categories": summary_rows(category_facts, "category", income_only=report == "income", spending_only=report != "income"),
        "accounts": summary_rows(facts, "account"),
        "people": summary_rows(facts, "person", spending_only=True),
        "types": summary_rows(facts, "type"),
        "people_owed": [],
        "people_payable": [],
        "category_comparison": [],
    }
    if transfers:
        breakdowns["types"].append({"key": "transfer", "label": "Transfer", "amount": metrics["transfer_volume"], "count": len(transfers), "debit": metrics["transfer_volume"], "credit": metrics["transfer_volume"], "spending": Decimal("0"), "income": Decimal("0")})
    if comparison:
        current_categories = {row["key"]: row for row in summary_rows(facts, "category", spending_only=True)}
        for key in current_categories.keys() | previous_categories.keys():
            current = current_categories.get(key)
            previous = previous_categories.get(key)
            spending = current["spending"] if current else Decimal("0")
            prior = previous["spending"] if previous else Decimal("0")
            breakdowns["category_comparison"].append({"key": key, "label": (current or previous)["label"], "spending": spending, "previous_spending": prior, "spending_change": spending - prior})
        breakdowns["category_comparison"].sort(key=lambda row: (-max(row["spending"], row["previous_spending"]), row["label"]))
    pivot = None
    if report == "overview":
        rows = sorted((transaction_row(fact) for fact in facts if fact.type == "expense" and fact.direction == "debit"), key=lambda row: row["amount"], reverse=True)[:10]
    elif report == "spending":
        spending = [fact for fact in facts if fact.type == "expense" and fact.direction == "debit"]
        metrics["expense_count"] = len(spending)
        rows = [transaction_row(fact) for fact in spending]
    elif report == "income":
        income = [fact for fact in facts if fact.type == "income" and fact.direction == "credit"]
        metrics["income_count"] = len(income)
        metrics["largest_income"] = max((fact.amount for fact in income), default=Decimal("0"))
        rows = [transaction_row(fact) for fact in income]
    elif report == "categories":
        rows = summary_rows([fact for fact in facts if fact.type in {"expense", "income"}], "category")
        metrics["categories_used"] = len(rows)
        metrics["uncategorized_count"] = sum(1 for fact in facts if fact.type in {"expense", "income"} and not fact.category_id)
    elif report == "accounts":
        rows = summary_rows(facts, "account")
        by_id = {row["key"]: row for row in rows}
        for transfer in transfers:
            for account_id, name in ((transfer["from_account_id"], transfer["from_account"]), (transfer["to_account_id"], transfer["to_account"])):
                key = str(account_id)
                if key not in by_id:
                    row = {"key": key, "label": name, "amount": Decimal("0"), "count": 0, "debit": Decimal("0"), "credit": Decimal("0"), "spending": Decimal("0"), "income": Decimal("0")}
                    rows.append(row)
                    by_id[key] = row
        for row in rows:
            account_transfers = [transfer for transfer in transfers if str(transfer["from_account_id"]) == row["key"] or str(transfer["to_account_id"]) == row["key"]]
            row["transfer_volume"] = sum((transfer["amount"] for transfer in account_transfers), Decimal("0"))
            row["count"] += len(account_transfers)
        metrics["accounts_used"] = len(rows)
    elif report == "people":
        lifetime = await load_facts(db, user.id, filters, user.timezone, settlement=True)
        rows = people_rows(facts, lifetime)
        metrics["owed_to_you"] = sum((row["owed_to_you"] for row in rows), Decimal("0"))
        metrics["you_owe"] = sum((row["you_owe"] for row in rows), Decimal("0"))
        metrics["people_with_activity"] = len(rows)
        breakdowns["people_owed"] = [{"key": row["key"], "label": row["label"], "amount": row["owed_to_you"], "count": row["transactions"]} for row in rows if row["owed_to_you"] > 0]
        breakdowns["people_payable"] = [{"key": row["key"], "label": row["label"], "amount": row["you_owe"], "count": row["transactions"]} for row in rows if row["you_owe"] > 0]
    elif report == "activity":
        rows = [transaction_row(fact) for fact in facts]
    elif report == "transfers":
        rows = transfers
        metrics["largest_transfer"] = max((row["amount"] for row in rows), default=Decimal("0"))
        metrics["accounts_involved"] = len({str(account_id) for row in rows for account_id in (row["from_account_id"], row["to_account_id"])})
    elif report == "types":
        rows = breakdowns["types"]
    elif report == "quality":
        rows = quality_rows(facts)
        metrics["quality_issues"] = len(rows)
        metrics["uncategorized_count"] = sum("Missing category" in row["issues"] for row in rows)
        metrics["missing_description_count"] = sum("Missing description" in row["issues"] for row in rows)
        metrics.update(await capture_quality_counts(db, user.id, filters, user.timezone))
    else:
        pivot = pivot_rows(facts, filters, user.timezone)
        rows = pivot["rows"]

    if report != "overview":
        rows = _sort_rows(rows, filters)
    count = len(rows)
    response = {
        "report": report,
        "currency": filters.currency,
        "date_from": filters.date_from,
        "date_to": filters.date_to,
        "metrics": metrics,
        "comparison": comparison,
        "trend": trend,
        "breakdowns": breakdowns,
        "rows": rows[filters.offset:filters.offset + filters.limit],
        "total": count,
        "limit": filters.limit,
        "offset": filters.offset,
        "has_next": filters.offset + filters.limit < count,
        "pivot_columns": pivot["columns"] if pivot else [],
    }
    return _json(response)
