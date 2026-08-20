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


async def create_conversation(client, token):
    response = await client.post(
        "/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Test Chat"},
    )

    return response.json()["id"]


@pytest.mark.asyncio
async def test_create_message(client):
    token = await register_and_login(client)
    conversation_id = await create_conversation(client, token)

    response = await client.post(
        f"/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Paid ₹500 for petrol"},
    )

    assert response.status_code == 201
    assert response.json()["role"] == "user"
    assert response.json()["content"] == "Paid ₹500 for petrol"


@pytest.mark.asyncio
async def test_get_messages(client):
    token = await register_and_login(client)
    conversation_id = await create_conversation(client, token)

    await client.post(
        f"/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "First message"},
    )

    await client.post(
        f"/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Second message"},
    )

    response = await client.get(
        f"/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["content"] == "First message"
    assert response.json()[1]["content"] == "Second message"


@pytest.mark.asyncio
async def test_get_message_by_id(client):
    token = await register_and_login(client)
    conversation_id = await create_conversation(client, token)

    created = await client.post(
        f"/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Hello"},
    )

    message_id = created.json()["id"]

    response = await client.get(
        f"/messages/{message_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == message_id
    assert response.json()["content"] == "Hello"


@pytest.mark.asyncio
async def test_message_not_found(client):
    token = await register_and_login(client)

    response = await client.get(
        "/messages/11111111-1111-1111-1111-111111111111",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_message_invalid_conversation(client):
    token = await register_and_login(client)

    response = await client.post(
        "/conversations/11111111-1111-1111-1111-111111111111/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Hello"},
    )

    assert response.status_code == 404