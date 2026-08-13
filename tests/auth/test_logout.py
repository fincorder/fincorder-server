import pytest


@pytest.mark.asyncio
async def test_logout_success(client):
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
        "/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    me = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me.status_code == 401


@pytest.mark.asyncio
async def test_logout_invalid_token(client):
    response = await client.post(
        "/auth/logout",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 200