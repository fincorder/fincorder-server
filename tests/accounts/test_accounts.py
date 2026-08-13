import pytest


@pytest.mark.asyncio
async def test_create_account(client):
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

    response = await client.post(
        "/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Travel",
            "currency": "INR",
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Travel"


@pytest.mark.asyncio
async def test_get_accounts(client):
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

    await client.post(
        "/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Travel",
            "currency": "INR",
        },
    )

    response = await client.get(
        "/accounts",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_update_account(client):
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

    created = await client.post(
        "/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Travel",
            "currency": "INR",
        },
    )

    account_id = created.json()["id"]

    response = await client.patch(
        f"/accounts/{account_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Vacation"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Vacation"


@pytest.mark.asyncio
async def test_delete_account(client):
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

    created = await client.post(
        "/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Travel",
            "currency": "INR",
        },
    )

    account_id = created.json()["id"]

    response = await client.delete(
        f"/accounts/{account_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204

    response = await client.get(
        "/accounts",
        headers={"Authorization": f"Bearer {token}"},
    )

    names = [account["name"] for account in response.json()]
    assert "Travel" not in names