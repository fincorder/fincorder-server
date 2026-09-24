"""One validated execution path shared by review and automatic capture."""
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.modules.capture.helpers import resolve_account_id, resolve_category_id, resolve_person_id
from app.modules.transactions.models import Transaction, TransactionType, TransactionDirection
from app.modules.transactions import service as transactions_service
from app.modules.transaction_groups import service as groups_service


def local_date(value, timezone_name):
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=ZoneInfo(timezone_name))


async def validate_transactions(db, user, transactions, expected_versions=None):
    if not transactions or len(transactions) > 30:
        raise ValueError("Provide between 1 and 30 transactions")
    prepared, versions, seen, transfer_groups = [], {}, set(), set()
    for txn in transactions:
        if txn.operation in {"update", "delete"}:
            if not txn.transaction_id or txn.transaction_id in seen:
                raise ValueError("Choose a distinct transaction for each update or archive")
            seen.add(txn.transaction_id)
            current = await db.scalar(select(Transaction).where(Transaction.id == txn.transaction_id, Transaction.user_id == user.id, Transaction.deleted_at.is_(None)).with_for_update().execution_options(populate_existing=True))
            if not current:
                raise ValueError("The transaction was not found or is already archived")
            if current.type == TransactionType.TRANSFER:
                transfer_groups.add(current.transaction_group_id)
            version = current.updated_at.isoformat()
            versions[str(current.id)] = version
            if expected_versions and expected_versions.get(str(current.id)) != version:
                raise ValueError("This transaction has changed since the proposal was created. Request a fresh proposal.")
            if txn.operation == "delete":
                prepared.append((txn, {}))
                continue
        else:
            if txn.transaction_id:
                raise ValueError("A new transaction cannot reference an existing transaction")
            current = None

        values = {}
        for field in ("type", "direction", "amount", "currency", "description", "transaction_date"):
            value = getattr(txn, field)
            if value is not None:
                values[field] = value
        if txn.account or txn.operation == "create":
            values["account_id"] = await resolve_account_id(db, user.id, txn.account)
        for field, resolver in (("category", resolve_category_id), ("person", resolve_person_id)):
            name = getattr(txn, field)
            if name:
                entity_id = await resolver(db, user.id, name)
                if entity_id is None:
                    raise ValueError(f"Transaction {len(prepared) + 1}: {field.title()} '{name}' was not found. Add it in settings or choose an existing one.")
                values[f"{field}_id"] = entity_id
        for field in txn.clear_fields:
            if field not in {"category", "person", "description"}:
                raise ValueError("Only category, person and description can be cleared")
            values[f"{field}_id" if field != "description" else field] = None
        if not values:
            raise ValueError("Specify what to change")
        effective = lambda field: values.get(field, getattr(current, field, None))
        amount = effective("amount")
        if amount is None or not Decimal(str(amount)).is_finite() or amount <= 0 or amount >= Decimal("10000000000") or amount != amount.quantize(Decimal("0.01")):
            raise ValueError(f"Transaction {len(prepared) + 1}: Amount must be positive with no more than two decimal places")
        currency = effective("currency")
        if not currency or len(currency) != 3 or not currency.isascii() or not currency.isalpha():
            raise ValueError(f"Transaction {len(prepared) + 1}: Use a three-letter currency code")
        kind, direction = effective("type"), effective("direction")
        if current is not None and current.type != TransactionType.TRANSFER and kind == "transfer":
            raise ValueError("Create a new paired transfer instead of converting a single transaction")
        if not kind or not direction:
            raise ValueError("Transaction type and debit/credit direction are required")
        if (kind in {"expense", "lend"} and direction != "debit") or (kind in {"income", "borrow"} and direction != "credit"):
            raise ValueError("Expense/lending must be debit; income/borrowing must be credit")
        if kind in {"lend", "borrow", "repayment"} and not effective("person_id"):
            raise ValueError(f"Transaction {len(prepared) + 1}: Choose a person for lending, borrowing or repayment")
        if kind in {"expense", "income"} and not (effective("description") or effective("category_id")):
            raise ValueError(f"Transaction {len(prepared) + 1}: Describe what this was for or choose a category")
        if "type" in values:
            values["type"] = TransactionType(values["type"])
        if "direction" in values:
            values["direction"] = TransactionDirection(values["direction"])
        if "currency" in values:
            values["currency"] = values["currency"].upper()
        if "transaction_date" in values:
            try:
                values["transaction_date"] = local_date(values["transaction_date"], user.timezone)
            except (ValueError, TypeError) as exc:
                raise ValueError("Use a valid transaction date") from exc
        if txn.operation == "create" and "transaction_date" not in values:
            raise ValueError("Transaction date is required")
        prepared.append((txn, values))

    batches = [[v for t, v in prepared if t.operation == "create" and t.type == "transfer"]]
    for group_id in transfer_groups:
        existing = list(await db.scalars(select(Transaction).where(Transaction.transaction_group_id == group_id, Transaction.user_id == user.id, Transaction.type == TransactionType.TRANSFER, Transaction.deleted_at.is_(None)).order_by(Transaction.id).with_for_update()))
        effective_entries = []
        for entry in existing:
            operation = next(((t, v) for t, v in prepared if t.transaction_id == entry.id), None)
            if operation and operation[0].operation == "delete":
                continue
            values = {field: getattr(entry, field) for field in ("amount", "currency", "direction", "account_id", "type")}
            if operation:
                values.update(operation[1])
            if values["type"] != TransactionType.TRANSFER:
                raise ValueError("A transfer entry cannot be changed into a different transaction type")
            effective_entries.append(values)
        batches.append(effective_entries)
    for transfers in batches:
        if len(transfers) % 2:
            raise ValueError("A transfer needs both its debit and credit entries")
        remaining = list(transfers)
        while remaining:
            first = remaining.pop(0)
            other = next((v for v in remaining if v["direction"] != first["direction"] and v["amount"] == first["amount"] and v["currency"] == first["currency"] and v["account_id"] != first["account_id"]), None)
            if other is None:
                raise ValueError("Transfer entries need equal amounts/currency and different source and destination accounts")
            remaining.remove(other)
    return prepared, versions


async def apply_transactions(db, user, event, transactions, expected_versions=None):
    prepared, _ = await validate_transactions(db, user, transactions, expected_versions)
    group = None
    if any(t.operation == "create" for t in transactions):
        group = await groups_service.create_transaction_group(db, event.id, commit=False)
    ids, before = [], {}
    for txn, values in prepared:
        if txn.operation != "create":
            current = await transactions_service.get_transaction(db, txn.transaction_id, user.id)
            before[str(current.id)] = {field: str(getattr(current, field)) if getattr(current, field) is not None else None for field in ("amount", "currency", "account_id", "category_id", "person_id", "type", "direction", "description", "transaction_date")}
        if txn.operation == "delete":
            await transactions_service.delete_transaction(db, txn.transaction_id, user.id, commit=False)
            ids.append(txn.transaction_id)
        elif txn.operation == "update":
            await transactions_service.update_transaction(db, txn.transaction_id, user.id, commit=False, **values)
            ids.append(txn.transaction_id)
        else:
            values["transaction_type"] = values.pop("type")
            for field in ("category_id", "person_id", "description"):
                values.setdefault(field, None)
            transaction = await transactions_service.create_transaction(db, transaction_group_id=group.id, user_id=user.id, commit=False, **values)
            ids.append(transaction.id)
    if group:
        await groups_service.mark_posted(db, group, commit=False)
    return ids, before
