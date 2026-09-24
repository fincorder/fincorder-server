from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from app.modules.reports.filters import ReportFilters, timezone_for
from app.modules.reports.repository import Fact

ZERO = Decimal("0")


def total(facts: list[Fact]) -> Decimal:
    return sum((fact.amount for fact in facts), ZERO)


def local_period(value: datetime, granularity: str, timezone_name: str | None) -> str:
    day = value.astimezone(timezone_for(timezone_name)).date()
    if granularity == "day":
        return day.isoformat()
    if granularity == "week":
        year, week, _ = day.isocalendar()
        return f"{year}-W{week:02d}"
    return day.strftime("%Y-%m")


def base_metrics(facts: list[Fact], transfers: list[dict]) -> dict:
    by_kind = lambda kind, direction: [fact for fact in facts if fact.type == kind and fact.direction == direction]
    expense = total(by_kind("expense", "debit"))
    income = total(by_kind("income", "credit"))
    lent = total(by_kind("lend", "debit"))
    borrowed = total(by_kind("borrow", "credit"))
    repayment_sent = total(by_kind("repayment", "debit"))
    repayment_received = total(by_kind("repayment", "credit"))
    return {
        "spending": expense,
        "income": income,
        "net_flow": income - expense - lent + borrowed - repayment_sent + repayment_received,
        "transactions": len(facts) - sum(1 for fact in facts if fact.type == "transfer") + len(transfers),
        "average_expense": expense / len(by_kind("expense", "debit")) if by_kind("expense", "debit") else ZERO,
        "largest_expense": max((fact.amount for fact in by_kind("expense", "debit")), default=ZERO),
        "lent": lent,
        "borrowed": borrowed,
        "repayment_sent": repayment_sent,
        "repayment_received": repayment_received,
        "transfer_volume": sum((item["amount"] for item in transfers), ZERO),
        "transfer_count": len(transfers),
    }


def summary_rows(facts: list[Fact], dimension: str, *, spending_only: bool = False, income_only: bool = False) -> list[dict]:
    groups: dict[str, dict] = {}
    for fact in facts:
        if fact.type == "transfer" or (spending_only and not (fact.type == "expense" and fact.direction == "debit")) or (income_only and not (fact.type == "income" and fact.direction == "credit")):
            continue
        key = str(getattr(fact, f"{dimension}_id")) if dimension in {"account", "category", "person"} else fact.type
        label = getattr(fact, dimension) if dimension in {"account", "category", "person"} else fact.type.title()
        fallback = "Uncategorized" if dimension == "category" else "Unassigned"
        row = groups.setdefault(key, {"key": key, "label": label or fallback, "amount": ZERO, "count": 0, "debit": ZERO, "credit": ZERO, "spending": ZERO, "income": ZERO})
        row["amount"] += fact.amount
        row["count"] += 1
        row[fact.direction] += fact.amount
        if fact.type == "expense" and fact.direction == "debit":
            row["spending"] += fact.amount
        if fact.type == "income" and fact.direction == "credit":
            row["income"] += fact.amount
    return sorted(groups.values(), key=lambda row: (-row["amount"], row["label"]))


def trend_rows(facts: list[Fact], transfers: list[dict], granularity: str, timezone_name: str | None) -> list[dict]:
    rows = defaultdict(lambda: {"period": "", "spending": ZERO, "income": ZERO, "lent": ZERO, "borrowed": ZERO, "repayment_sent": ZERO, "repayment_received": ZERO, "transfer_volume": ZERO, "count": 0})
    for fact in facts:
        if fact.type == "transfer":
            continue
        period = local_period(fact.transaction_date, granularity, timezone_name)
        row = rows[period]
        row["period"] = period
        row["count"] += 1
        if fact.type == "expense" and fact.direction == "debit":
            row["spending"] += fact.amount
        elif fact.type == "income" and fact.direction == "credit":
            row["income"] += fact.amount
        elif fact.type == "lend" and fact.direction == "debit":
            row["lent"] += fact.amount
        elif fact.type == "borrow" and fact.direction == "credit":
            row["borrowed"] += fact.amount
        elif fact.type == "repayment":
            row["repayment_sent" if fact.direction == "debit" else "repayment_received"] += fact.amount
    for transfer in transfers:
        period = local_period(transfer["transaction_date"], granularity, timezone_name)
        rows[period]["period"] = period
        rows[period]["transfer_volume"] += transfer["amount"]
        rows[period]["count"] += 1
    return [rows[key] for key in sorted(rows)]


def transfer_rows(facts: list[Fact], account_id=None, search: str | None = None) -> list[dict]:
    groups: dict[str, list[Fact]] = defaultdict(list)
    for fact in facts:
        if fact.type == "transfer":
            groups[str(fact.group_id)].append(fact)
    rows = []
    for group_id, legs in groups.items():
        debit = next((leg for leg in legs if leg.direction == "debit"), None)
        credit = next((leg for leg in legs if leg.direction == "credit"), None)
        if len(legs) != 2 or not debit or not credit or debit.amount != credit.amount or debit.account_id == credit.account_id:
            continue
        if account_id and account_id not in {debit.account_id, credit.account_id}:
            continue
        if search and search.lower() not in " ".join(filter(None, [debit.description, credit.description, debit.account, credit.account])).lower():
            continue
        rows.append({"id": group_id, "transaction_date": debit.transaction_date, "from_account": debit.account, "to_account": credit.account, "from_account_id": debit.account_id, "to_account_id": credit.account_id, "amount": debit.amount, "description": debit.description or credit.description})
    return sorted(rows, key=lambda row: row["transaction_date"], reverse=True)


def people_rows(facts: list[Fact], settlement_facts: list[Fact]) -> list[dict]:
    rows: dict[str, dict] = {}
    for fact in settlement_facts + facts:
        if not fact.person_id:
            continue
        key = str(fact.person_id)
        rows.setdefault(key, {"key": key, "label": fact.person or "Unknown person", "lent": ZERO, "borrowed": ZERO, "repaid_to_you": ZERO, "repaid_by_you": ZERO, "spending": ZERO, "transactions": 0, "last_activity": None})
    for fact in settlement_facts:
        if not fact.person_id:
            continue
        row = rows[str(fact.person_id)]
        if not row["last_activity"] or fact.transaction_date > row["last_activity"]:
            row["last_activity"] = fact.transaction_date
        if fact.type == "lend" and fact.direction == "debit":
            row["lent"] += fact.amount
        elif fact.type == "borrow" and fact.direction == "credit":
            row["borrowed"] += fact.amount
        elif fact.type == "repayment":
            row["repaid_to_you" if fact.direction == "credit" else "repaid_by_you"] += fact.amount
    for fact in facts:
        if not fact.person_id:
            continue
        row = rows[str(fact.person_id)]
        row["transactions"] += 1
        if fact.type == "expense" and fact.direction == "debit":
            row["spending"] += fact.amount
        if not row["last_activity"] or fact.transaction_date > row["last_activity"]:
            row["last_activity"] = fact.transaction_date
    for row in rows.values():
        row["owed_to_you"] = row["lent"] - row["repaid_to_you"]
        row["you_owe"] = row["borrowed"] - row["repaid_by_you"]
        row["net_position"] = row["owed_to_you"] - row["you_owe"]
    return sorted(rows.values(), key=lambda row: (-max(row["owed_to_you"], row["you_owe"], row["spending"]), row["label"]))


def transaction_row(fact: Fact) -> dict:
    return {"id": fact.id, "transaction_date": fact.transaction_date, "description": fact.description, "type": fact.type, "direction": fact.direction, "amount": fact.amount, "account": fact.account, "category": fact.category, "person": fact.person, "group_id": fact.group_id}


def quality_rows(facts: list[Fact]) -> list[dict]:
    rows = []
    for fact in facts:
        issues = []
        if fact.type in {"expense", "income"} and not fact.category_id:
            issues.append("Missing category")
        if not fact.description or not fact.description.strip():
            issues.append("Missing description")
        if fact.account_deleted:
            issues.append("Archived account")
        if fact.type in {"lend", "borrow", "repayment"} and not fact.person_id:
            issues.append("Missing person")
        if issues:
            rows.append({**transaction_row(fact), "issues": issues})
    return rows


def pivot_rows(facts: list[Fact], filters: ReportFilters, timezone_name: str | None) -> dict:
    def dimension(fact: Fact, name: str) -> str:
        if name == "month":
            return local_period(fact.transaction_date, "month", timezone_name)
        if name == "type":
            return fact.type.title()
        return getattr(fact, name) or "Unassigned"

    matrix: dict[str, dict[str, list[Fact]]] = defaultdict(lambda: defaultdict(list))
    for fact in facts:
        if fact.type != "transfer":
            matrix[dimension(fact, filters.pivot_row)][dimension(fact, filters.pivot_column)].append(fact)
    columns = sorted({column for row in matrix.values() for column in row})

    def measure(group: list[Fact]):
        if filters.pivot_measure == "count":
            return len(group)
        if filters.pivot_measure == "average":
            return total(group) / len(group) if group else ZERO
        if filters.pivot_measure in {"debit", "credit"}:
            return total([fact for fact in group if fact.direction == filters.pivot_measure])
        return total(group)

    rows = [{"label": label, "cells": {column: measure(groups.get(column, [])) for column in columns}, "total": measure([fact for group in groups.values() for fact in group])} for label, groups in matrix.items()]
    rows.sort(key=lambda row: (-row["total"], row["label"]))
    return {"columns": columns, "rows": rows}
