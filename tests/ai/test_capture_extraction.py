from decimal import Decimal

import pytest

from app.ai.openai_provider import OpenAIProvider


CONTEXT = {
    "today": "2026-08-31",
    "accounts": [
        "Salary Account",
        "Spending Account",
        "Cash",
    ],
    "categories": [
        "Food",
        "Transport",
        "Shopping",
        "Bills",
        "Entertainment",
    ],
    "people": [
        "Fouzan",
        "Ahmed",
    ],
    "messages": [],
}


@pytest.mark.asyncio
async def test_extract_simple_expense():
    provider = OpenAIProvider()

    result = await provider.extract_financial_event(
        message="Paid ₹500 for petrol",
        context=CONTEXT,
    )

    assert result.status == "completed"
    assert len(result.transactions) == 1

    transaction = result.transactions[0]

    assert transaction.type == "expense"
    assert transaction.amount == Decimal("500")
    assert transaction.currency == "INR"
    assert transaction.category == "Transport"
    assert transaction.direction == "debit"


@pytest.mark.asyncio
async def test_extract_multiple_transactions():
    provider = OpenAIProvider()

    result = await provider.extract_financial_event(
        message=(
            "Spent Rs.500 on outing with Fouzan today and Fouzan has to "
            "return me Rs.250. Also, spent Rs.100 on petrol for scooter. "
            "Rs.40 for metro parking yesterday"
        ),
        context=CONTEXT,
    )

    assert result.status == "completed"
    assert len(result.transactions) == 4

    amounts = sorted(
        transaction.amount
        for transaction in result.transactions
    )

    assert amounts == [
        Decimal("40"),
        Decimal("100"),
        Decimal("250"),
        Decimal("500"),
    ]


@pytest.mark.asyncio
async def test_extract_salary_income():
    provider = OpenAIProvider()

    result = await provider.extract_financial_event(
        message="Got ₹50,000 salary today",
        context=CONTEXT,
    )

    assert result.status == "completed"
    assert len(result.transactions) == 1

    transaction = result.transactions[0]

    assert transaction.type == "income"
    assert transaction.amount == Decimal("50000")
    assert transaction.direction == "credit"


@pytest.mark.asyncio
async def test_extract_transfer():
    provider = OpenAIProvider()

    result = await provider.extract_financial_event(
        message="Transferred ₹10,000 from Salary Account to Spending Account",
        context=CONTEXT,
    )

    assert result.status == "completed"
    assert len(result.transactions) == 2

    assert all(
        transaction.type == "transfer"
        for transaction in result.transactions
    )

    assert sorted(
        transaction.amount
        for transaction in result.transactions
    ) == [
        Decimal("10000"),
        Decimal("10000"),
    ]

    accounts = {
        transaction.account
        for transaction in result.transactions
    }

    assert accounts == {
        "Salary Account",
        "Spending Account",
    }


@pytest.mark.asyncio
async def test_extract_lending():
    provider = OpenAIProvider()

    result = await provider.extract_financial_event(
        message="Lent ₹2,000 to Fouzan",
        context=CONTEXT,
    )

    assert result.status == "completed"
    assert len(result.transactions) == 1

    transaction = result.transactions[0]

    assert transaction.type == "lend"
    assert transaction.amount == Decimal("2000")
    assert transaction.person == "Fouzan"
    assert transaction.direction == "debit"


@pytest.mark.asyncio
async def test_extract_repayment():
    provider = OpenAIProvider()

    result = await provider.extract_financial_event(
        message="Fouzan returned ₹1,000",
        context=CONTEXT,
    )

    assert result.status == "completed"
    assert len(result.transactions) == 1

    transaction = result.transactions[0]

    assert transaction.type == "repayment"
    assert transaction.amount == Decimal("1000")
    assert transaction.person == "Fouzan"
    assert transaction.direction == "credit"


@pytest.mark.asyncio
async def test_extract_missing_information():
    provider = OpenAIProvider()

    result = await provider.extract_financial_event(
        message="Paid ₹500",
        context=CONTEXT,
    )

    assert result.status == "needs_clarification"
    assert "category" in result.missing_fields
    assert len(result.transactions) == 0