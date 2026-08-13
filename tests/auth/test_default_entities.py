import pytest


@pytest.mark.asyncio
async def test_register_creates_default_accounts(client):
    await client.post(
        "/auth/register",
        json={
            "name": "Aashir",
            "email": "aashir@example.com",
            "password": "password123",
        },
    )

    login = await client.post(
        "/auth/login",
        json={
            "email": "aashir@example.com",
            "password": "password123",
        },
    )

    token = login.json()["access_token"]

    response = await client.get(
        "/accounts",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    names = {account["name"] for account in response.json()}

    assert names == {
        "Salary Account",
        "Spending Account",
        "Cash",
    }


@pytest.mark.asyncio
async def test_register_creates_default_categories(client):
    await client.post(
        "/auth/register",
        json={
            "name": "Aashir",
            "email": "aashir@example.com",
            "password": "password123",
        },
    )

    login = await client.post(
        "/auth/login",
        json={
            "email": "aashir@example.com",
            "password": "password123",
        },
    )

    token = login.json()["access_token"]

    response = await client.get(
        "/categories",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    categories = {(c["name"], c["type"]) for c in response.json()}

    expected = {
        ("Food", "expense"),
        ("Transport", "expense"),
        ("Shopping", "expense"),
        ("Bills", "expense"),
        ("Entertainment", "expense"),
        ("Health", "expense"),
        ("Other", "expense"),
        ("Salary", "income"),
        ("Freelance", "income"),
        ("Gift", "income"),
        ("Refund", "income"),
        ("Other", "income"),
    }

    assert categories == expected