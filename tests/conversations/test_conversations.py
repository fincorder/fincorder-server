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
async def test_create_conversation(client):
    token = await register_and_login(client)

    response = await client.post(
        "/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "August Expenses"},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "August Expenses"
    assert response.json()["status"] == "active"


@pytest.mark.asyncio
async def test_get_conversations(client):
    token = await register_and_login(client)

    await client.post(
        "/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "August Expenses"},
    )

    response = await client.get(
        "/conversations",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_get_conversation_by_id(client):
    token = await register_and_login(client)

    created = await client.post(
        "/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "August Expenses"},
    )

    conversation_id = created.json()["id"]

    response = await client.get(
        f"/conversations/{conversation_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == conversation_id


@pytest.mark.asyncio
async def test_update_conversation(client):
    token = await register_and_login(client)

    created = await client.post(
        "/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "August Expenses"},
    )

    conversation_id = created.json()["id"]

    response = await client.patch(
        f"/conversations/{conversation_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "September Expenses"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "September Expenses"


@pytest.mark.asyncio
async def test_archive_conversation(client):
    token = await register_and_login(client)

    created = await client.post(
        "/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "August Expenses"},
    )

    conversation_id = created.json()["id"]

    response = await client.patch(
        f"/conversations/{conversation_id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_archived_conversation_is_removed_from_active_list(client):
    token = await register_and_login(client)

    created = await client.post(
        "/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Temporary Chat"},
    )
    conversation_id = created.json()["id"]

    response = await client.patch(
        f"/conversations/{conversation_id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "archived"

    listed = await client.get(
        "/conversations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert all(conversation["id"] != conversation_id for conversation in listed.json())

    archived = await client.get(
        f"/conversations/{conversation_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert archived.status_code == 404


@pytest.mark.asyncio
async def test_conversation_not_found(client):
    token = await register_and_login(client)

    response = await client.get(
        "/conversations/11111111-1111-1111-1111-111111111111",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
