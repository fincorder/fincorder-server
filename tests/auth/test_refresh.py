import pytest


@pytest.mark.asyncio
async def test_refresh_success(client):
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

    old_token = login.json()["access_token"]

    refresh = await client.post(
        "/auth/refresh",
        headers={"Authorization": f"Bearer {old_token}"},
    )

    assert refresh.status_code == 200

    new_token = refresh.json()["access_token"]
    assert new_token != old_token

    old_me = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {old_token}"},
    )

    assert old_me.status_code == 401

    new_me = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {new_token}"},
    )

    assert new_me.status_code == 200


@pytest.mark.asyncio
async def test_refresh_invalid_token(client):
    response = await client.post(
        "/auth/refresh",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401