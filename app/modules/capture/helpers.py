import re
from datetime import datetime, timezone
from decimal import Decimal

from app.modules.accounts import repository as accounts_repository
from app.modules.categories import repository as categories_repository
from app.modules.people import repository as people_repository


_AMOUNT_WITH_CURRENCY = re.compile(
    r"(?:₹|rs\.?|inr)\s*([0-9][0-9,]*(?:\.[0-9]+)?)|"
    r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:rs\.?|inr)",
    re.IGNORECASE,
)
_AMOUNT_AFTER_ACTION = re.compile(
    r"\b(?:spent|paid|received|got|borrowed|lent|transferred|transfer|cost)"
    r"\s+(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
    re.IGNORECASE,
)
_CORRECTION_TARGET = re.compile(
    r"\b(?:not|instead of|rather than)\s+(?:₹|rs\.?|inr)?\s*"
    r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(lakh|lakhs|crore|crores|k)?",
    re.IGNORECASE,
)


def extract_explicit_amount(message: str) -> Decimal | None:
    """Extract an amount only when the user explicitly states one."""
    # Exclude the OLD value in corrections, and never truncate 1.2k to 1.2.
    text = _CORRECTION_TARGET.sub("", message)
    number = r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(lakh|lakhs|crore|crores|k)?"
    pattern = re.compile(r"(?:₹|rs\.?|inr|\bspent|\bpaid|\breceived|\bgot|\blent|\bborrowed|\btransferred|\bcost)\s*" + number + r"|" + number + r"\s*(?:rs\.?|inr)\b", re.I)
    amounts = []
    for match in pattern.finditer(text):
        first, first_unit, second, second_unit = match.groups()
        value, unit = (first, first_unit) if first else (second, second_unit)
        multiplier = {"k": 1000, "lakh": 100000, "lakhs": 100000, "crore": 10000000, "crores": 10000000}.get((unit or "").lower(), 1)
        amounts.append(Decimal(value.replace(",", "")) * multiplier)
    if not amounts and re.fullmatch(r"\s*\d+(?:\.\d+)?\s*", text):
        return Decimal(text.strip())
    return amounts[0] if len(amounts) == 1 else None


def extract_correction_target_amount(message: str) -> Decimal | None:
    """Extract the old amount in an explicit correction such as 'not 500'."""
    match = _CORRECTION_TARGET.search(message)
    if not match:
        return None

    try:
        multiplier = {"k": 1000, "lakh": 100000, "lakhs": 100000, "crore": 10000000, "crores": 10000000}.get((match.group(2) or "").lower(), 1)
        return Decimal(match.group(1).replace(",", "")) * multiplier
    except ArithmeticError:
        return None


def infer_partial_transaction(message: str) -> dict:
    """Keep deterministic facts from a clarification-starting message."""
    amount = extract_explicit_amount(message)
    if amount is None:
        return {}

    normalized = message.lower()
    if any(word in normalized for word in ("salary", "received", "got ", "income")):
        transaction_type, direction = "income", "credit"
    elif "lent" in normalized:
        transaction_type, direction = "lend", "debit"
    elif "borrow" in normalized:
        transaction_type, direction = "borrow", "credit"
    elif "transfer" in normalized:
        transaction_type, direction = "transfer", None
    else:
        transaction_type, direction = "expense", "debit"

    return {
        "operation": "create",
        "transaction_id": None,
        "type": transaction_type,
        "amount": str(amount),
        "currency": "INR",
        "account": None,
        "category": None,
        "person": None,
        "description": None,
        "transaction_date": None,
        "clear_fields": [],
        "direction": direction,
    }


def format_amount(amount: Decimal | str | int | float) -> str:
    value = Decimal(str(amount)).normalize()
    return format(value, "f")


def replace_assistant_amounts(message: str, amount: Decimal | str | int | float) -> str:
    """Correct stale currency mentions in an assistant clarification/reply."""
    formatted_amount = format_amount(amount)
    return re.sub(
        r"(?:₹\s*[0-9][0-9,]*(?:\.[0-9]+)?|rs\.?\s*[0-9][0-9,]*(?:\.[0-9]+)?|inr\s*[0-9][0-9,]*(?:\.[0-9]+)?)",
        f"₹{formatted_amount}",
        message,
        flags=re.IGNORECASE,
    )


def parse_transaction_date(value: str) -> datetime:
    """Convert AI date text to a database timestamp; assume UTC without an offset."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


async def resolve_account_id(db, user_id, name):
    accounts = await accounts_repository.get_accounts(db, user_id)

    if name:
        for account in accounts:
            if account.name.lower() == name.lower():
                return account.id

        raise ValueError(f"Account '{name}' not found")

    for account in accounts:
        if account.is_default:
            return account.id

    for account in accounts:
        if account.name.lower() == "spending account":
            return account.id

    if accounts:
        return accounts[0].id

    raise ValueError("Account not found")


async def resolve_category_id(db, user_id, name):
    if not name:
        return None

    categories = await categories_repository.get_categories(db, user_id)

    for category in categories:
        if category.name.lower() == name.lower():
            return category.id

    return None


async def resolve_person_id(db, user_id, name):
    if not name:
        return None

    people = await people_repository.get_people(db, user_id)

    for person in people:
        if person.name.lower() == name.lower():
            return person.id

    return None
