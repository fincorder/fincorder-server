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
async def test_create_person(client):
    token = await register_and_login(client)

    response = await client.post(
        "/people",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Ahmed"},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Ahmed"


@pytest.mark.asyncio
async def test_get_people(client):
    token = await register_and_login(client)

    await client.post(
        "/people",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Ahmed"},
    )

    response = await client.get(
        "/people",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_update_person(client):
    token = await register_and_login(client)

    created = await client.post(
        "/people",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Ahmed"},
    )

    person_id = created.json()["id"]

    response = await client.patch(
        f"/people/{person_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Rahman"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Rahman"


@pytest.mark.asyncio
async def test_delete_person(client):
    token = await register_and_login(client)

    created = await client.post(
        "/people",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Ahmed"},
    )

    person_id = created.json()["id"]

    response = await client.delete(
        f"/people/{person_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204

    response = await client.get(
        "/people",
        headers={"Authorization": f"Bearer {token}"},
    )

    names = [person["name"] for person in response.json()]
    assert "Ahmed" not in names


@pytest.mark.asyncio
async def test_duplicate_person(client):
    token = await register_and_login(client)

    await client.post(
        "/people",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Ahmed"},
    )

    response = await client.post(
        "/people",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Ahmed"},
    )

    assert response.status_code == 409