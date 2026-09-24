"""Deterministic defaults and multi-turn draft merging, independent of the LLM."""
import re
from uuid import uuid4

from app.ai.schemas import AITransaction, CaptureAIResponse
from app.modules.capture.helpers import extract_explicit_amount, infer_partial_transaction


def validation_missing_field(error):
    field = next((field for field in ("account", "category", "person", "amount", "currency", "direction", "date") if field in error.lower()), "transfer_entries" if "transfer" in error.lower() else "transaction_id")
    if "describe what" in error.lower():
        field = "description"
    if field == "date":
        field = "transaction_date"
    index = re.search(r"Transaction (\d+):", error)
    return f"{int(index[1]) - 1}.{field}" if index else field


def starts_new_transaction(message: str) -> bool:
    return bool(re.search(r"\b(spent|paid|bought|lent|borrowed|received|transferred|earned)\b", message, re.I)) and not bool(re.search(r"\b(actually|instead|correction|not|change|correct)\b", message, re.I))


def prepare_response(response: CaptureAIResponse, message: str, context: dict, pending=None) -> CaptureAIResponse:
    transactions = response.transactions
    explicit = extract_explicit_amount(message)
    if pending:
        stored = (pending.extracted_data or {}).get("transactions", [])
        by_id = {t.draft_id: t for t in transactions if t.draft_id}
        merged = []
        for index, previous in enumerate(stored):
            current = by_id.get(previous.get("draft_id"))
            if current is None and previous.get("transaction_id"):
                current = next((t for t in transactions if str(t.transaction_id) == previous["transaction_id"]), None)
            if current is None and len(stored) == 1 and len(transactions) == 1:
                current = transactions[0]
            draft = dict(previous)
            if current:
                updates = current.model_dump()
                for field, value in updates.items():
                    if field in {"operation", "draft_id", "changed_fields"} or (field == "transaction_id" and draft.get("transaction_id")):
                        continue
                    validation_error = (pending.extracted_data or {}).get("validation_error", "") or ""
                    missing_fields = list(pending.missing_fields or []) + ([validation_missing_field(validation_error)] if validation_error else [])
                    missing = field in missing_fields or f"{index}.{field}" in missing_fields
                    corrected = field in current.changed_fields and bool(re.search(r"\b(actually|instead|not|change|correct|make it)\b", message, re.I))
                    if field in {"account", "category", "person"} and isinstance(value, str):
                        names = [word for word in re.findall(r"\w+", value.lower()) if len(word) >= 3 and word not in {"account", "bank"}]
                        corrected = corrected or any(re.search(rf"\b{re.escape(word)}\b", message.lower()) for word in names)
                    if field == "transaction_date" and field in current.changed_fields:
                        corrected = corrected or bool(re.search(r"\b(today|yesterday|tomorrow|last|ago)\b|\d{4}-\d{2}-\d{2}", message, re.I))
                    if value is not None and (draft.get(field) is None or missing or corrected):
                        draft[field] = value
                if explicit is not None and len(stored) == 1:
                    draft["amount"] = explicit
            merged.append(AITransaction.model_validate(draft))
        if stored:
            if "transfer_entries" in (pending.missing_fields or []):
                known = {draft.get("draft_id") for draft in stored}
                targets = {draft.get("transaction_id") for draft in stored if draft.get("transaction_id")}
                merged.extend(t for t in transactions if t.draft_id not in known and str(t.transaction_id) not in targets)
            transactions = merged
    elif len(transactions) == 1 and explicit is not None and transactions[0].operation == "create":
        transactions = [transactions[0].model_copy(update={"amount": explicit})]
    elif len(transactions) == 2 and explicit is not None and all(t.operation == "create" and t.type == "transfer" for t in transactions):
        transactions = [t.model_copy(update={"amount": explicit}) for t in transactions]

    if not transactions and response.status == "needs_clarification" and not {"transaction_id", "draft"}.intersection(response.missing_fields):
        partial = infer_partial_transaction(message)
        if partial:
            transactions = [AITransaction.model_validate(partial)]

    accounts = context.get("account_details", [])
    result = []
    for transaction in transactions:
        updates = {"draft_id": transaction.draft_id or str(uuid4())}
        if transaction.operation == "create":
            if not transaction.account:
                updates["account"] = context.get("default_account")
            account_name = updates.get("account", transaction.account)
            account = next((a for a in accounts if a["name"] == account_name), {})
            if not transaction.currency:
                updates["currency"] = account.get("currency", "INR")
            if not transaction.transaction_date:
                updates["transaction_date"] = context["today"]
        result.append(transaction.model_copy(update=updates))
    return response.model_copy(update={"transactions": result})
