import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    response = await client.post(
        "/auth/register",
        json={
            "name": "Aashir",
            "email": "aashir@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Aashir"
    assert data["status"] == "active"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {
        "name": "Aashir",
        "email": "aashir@example.com",
        "password": "password123",
    }

    await client.post("/auth/register", json=payload)

    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_invalid_email(client):
    response = await client.post(
        "/auth/register",
        json={
            "name": "Aashir",
            "email": "invalid-email",
            "password": "password123",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(client):
    response = await client.post(
        "/auth/register",
        json={
            "name": "Aashir",
            "email": "aashir@example.com",
            "password": "123",
        },
    )

    assert response.status_code == 422