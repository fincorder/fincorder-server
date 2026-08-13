import pytest


async def register_and_login(client):
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

    return login.json()["access_token"]


@pytest.mark.asyncio
async def test_create_category(client):
    token = await register_and_login(client)

    response = await client.post(
        "/categories",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Food",
            "type": "expense",
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Food"
    assert response.json()["type"] == "expense"


@pytest.mark.asyncio
async def test_get_categories(client):
    token = await register_and_login(client)

    await client.post(
        "/categories",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Food",
            "type": "expense",
        },
    )

    response = await client.get(
        "/categories",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_update_category(client):
    token = await register_and_login(client)

    created = await client.post(
        "/categories",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Food",
            "type": "expense",
        },
    )

    category_id = created.json()["id"]

    response = await client.patch(
        f"/categories/{category_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Dining"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Dining"


@pytest.mark.asyncio
async def test_delete_category(client):
    token = await register_and_login(client)

    created = await client.post(
        "/categories",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Food",
            "type": "expense",
        },
    )

    category_id = created.json()["id"]

    response = await client.delete(
        f"/categories/{category_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204

    response = await client.get(
        "/categories",
        headers={"Authorization": f"Bearer {token}"},
    )

    names = [category["name"] for category in response.json()]
    assert "Food" not in names


@pytest.mark.asyncio
async def test_duplicate_category_same_type(client):
    token = await register_and_login(client)

    payload = {
        "name": "Food",
        "type": "expense",
    }

    await client.post(
        "/categories",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )

    response = await client.post(
        "/categories",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_same_name_different_type_allowed(client):
    token = await register_and_login(client)

    await client.post(
        "/categories",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Salary",
            "type": "income",
        },
    )

    response = await client.post(
        "/categories",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Salary",
            "type": "expense",
        },
    )

    assert response.status_code == 201