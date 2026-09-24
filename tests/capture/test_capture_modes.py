from decimal import Decimal
import asyncio
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.ai.schemas import AITransaction, CaptureAIResponse
from app.main import app
from app.modules.capture.dependencies import get_ai_provider
from app.modules.capture.helpers import extract_explicit_amount
from tests.capture.test_capture import register_and_login, auth, post_capture, expense, confirm


@pytest.fixture
def provider():
    provider = AsyncMock()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_ai_provider, None)


def completed(*transactions, event_id=None):
    return CaptureAIResponse(status="completed", transactions=list(transactions), assistant_message="Ready", confidence=0.99, continuation_event_id=event_id)


@pytest.mark.asyncio
async def test_automatic_create_update_archive_and_receipts(client, provider):
    token = await register_and_login(client)
    settings = await client.patch('/auth/me', headers=auth(token), json={"review_transactions": False, "timezone": "Asia/Kolkata"})
    assert settings.status_code == 200
    assert settings.json()["review_transactions"] is False
    provider.extract_financial_event.return_value = completed(expense(219, description="Airtel recharge"))
    request = {"message": "Spent 219 on Airtel recharge", "request_id": str(uuid4())}
    first = await client.post('/capture', headers=auth(token), json=request)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "completed"
    repeated = await client.post('/capture', headers=auth(token), json=request)
    assert repeated.json() == first.json()
    assert provider.extract_financial_event.await_count == 1
    tid = first.json()["transaction_ids"][0]
    provider.extract_financial_event.return_value = completed(AITransaction(operation="update", transaction_id=UUID(tid), amount=250))
    edited = await post_capture(client, token, "Change that to 250", first.json()["conversation_id"])
    assert edited.json()["status"] == "completed", edited.text
    assert (await client.get('/transactions', headers=auth(token))).json()[0]["amount"] == "250.00"
    provider.extract_financial_event.return_value = completed(AITransaction(operation="delete", transaction_id=UUID(tid)))
    archived = await post_capture(client, token, "Archive that transaction", first.json()["conversation_id"])
    assert archived.json()["status"] == "completed", archived.text
    assert (await client.get('/transactions', headers=auth(token))).json() == []


@pytest.mark.asyncio
async def test_draft_saved_rejected_and_linked_by_message(client, provider):
    token = await register_and_login(client)
    provider.extract_financial_event.return_value = completed(expense(100, description="Coffee"))
    first = (await post_capture(client, token, "Spent 100 on coffee")).json()
    proposals = first["proposed_transactions"]
    proposals[0]["description"] = "Coffee with a friend"
    saved = await client.patch(f"/capture/{first['financial_event_id']}/draft", headers=auth(token), json={"transactions": proposals, "revision": first["revision"]})
    assert saved.status_code == 200
    assert (await confirm(client, token, first)).status_code == 400  # stale revision
    rejected = await client.post(f"/capture/{first['financial_event_id']}/reject", headers=auth(token))
    assert rejected.json()["status"] == "rejected"
    events = (await client.get(f"/financial-events/conversation/{first['conversation_id']}", headers=auth(token))).json()
    assert events[0]["assistant_message_id"] == first["assistant_message_id"]
    assert events[0]["extracted_data"]["transactions"][0]["description"] == "Coffee with a friend"
    assert events[0]["status"] == "rejected"


@pytest.mark.asyncio
async def test_multiple_drafts_preserve_known_facts(client, provider):
    token = await register_and_login(client)
    provider.extract_financial_event.return_value = CaptureAIResponse(status="needs_clarification", transactions=[expense(200, account="Cash"), expense(350, account="Cash")], missing_fields=["0.description", "1.description"], assistant_message="What were these for?", confidence=.9)
    first = (await post_capture(client, token, "Spent 200 and 350 by cash")).json()
    assert len(first["proposed_transactions"]) == 2
    provider.extract_financial_event.return_value = completed(expense(500, description="Petrol"))
    independent = (await post_capture(client, token, "Paid 500 for petrol", first["conversation_id"])).json()
    assert independent["financial_event_id"] != first["financial_event_id"]
    originals = first["proposed_transactions"]
    provider.extract_financial_event.return_value = completed(*[expense(999, draft_id=t["draft_id"], account="Spending Account", description=description) for t, description in zip(originals, ["Coffee", "Outing"])], event_id=UUID(first["financial_event_id"]))
    continued = (await post_capture(client, token, "Coffee and outing", first["conversation_id"])).json()
    assert continued["financial_event_id"] == first["financial_event_id"]
    assert [t["amount"] for t in continued["proposed_transactions"]] == ["200", "350"]
    assert [t["account"] for t in continued["proposed_transactions"]] == ["Cash", "Cash"]
    assert [t["description"] for t in continued["proposed_transactions"]] == ["Coffee", "Outing"]
    assert (await confirm(client, token, continued)).status_code == 200


@pytest.mark.asyncio
async def test_batch_validation_prevents_partial_write(client, provider):
    token = await register_and_login(client)
    await client.patch('/auth/me', headers=auth(token), json={"review_transactions": False})
    provider.extract_financial_event.return_value = completed(expense(200, description="Coffee"), expense(-50, description="Invalid"))
    capture = (await post_capture(client, token, "Coffee and another purchase")).json()
    assert capture["status"] == "needs_clarification"
    assert (await client.get('/transactions', headers=auth(token))).json() == []
    assert (await confirm(client, token, capture)).status_code == 400
    assert (await client.get('/transactions', headers=auth(token))).json() == []


@pytest.mark.asyncio
async def test_duplicate_confirmation_and_target_protection(client, provider):
    token = await register_and_login(client)
    provider.extract_financial_event.return_value = completed(expense(200, description="Coffee"))
    capture = (await post_capture(client, token, "Spent 200 on coffee")).json()
    first = await confirm(client, token, capture)
    assert first.status_code == 200
    second = await confirm(client, token, capture)
    assert second.json() == first.json()
    assert len((await client.get('/transactions', headers=auth(token))).json()) == 1
    fresh = (await post_capture(client, token, "Spent 200 on coffee")).json()
    fresh["proposed_transactions"][0].update(operation="delete", transaction_id=first.json()["transaction_ids"][0])
    assert (await confirm(client, token, fresh)).status_code == 400


@pytest.mark.asyncio
async def test_stale_transaction_update_is_rejected(client, provider):
    token = await register_and_login(client)
    provider.extract_financial_event.return_value = completed(expense(200, description="Coffee"))
    first = (await post_capture(client, token, "Spent 200 on coffee")).json()
    tid = (await confirm(client, token, first)).json()["transaction_ids"][0]
    provider.extract_financial_event.return_value = completed(AITransaction(operation="update", transaction_id=UUID(tid), amount=300))
    update = (await post_capture(client, token, "Change coffee to 300", first["conversation_id"])).json()
    await client.patch(f'/transactions/{tid}', headers=auth(token), json={"amount": "250"})
    assert (await confirm(client, token, update)).status_code == 400
    assert (await client.get(f'/transactions/{tid}', headers=auth(token))).json()["amount"] == "250.00"


@pytest.mark.parametrize(('message', 'expected'), [('Spent 1.2k on groceries', '1200'), ('Paid 2 lakh', '200000'), ('Not 500, I spent 219 rs only', '219'), ('219', '219'), ('Spent 200 and paid 350', None)])
def test_explicit_amounts(message, expected):
    assert extract_explicit_amount(message) == (Decimal(expected) if expected else None)


@pytest.mark.asyncio
async def test_simultaneous_confirmation_only_applies_once(client, provider):
    token = await register_and_login(client)
    provider.extract_financial_event.return_value = completed(expense(200, description="Coffee"))
    capture = (await post_capture(client, token, "Spent 200 on coffee")).json()
    results = await asyncio.gather(confirm(client, token, capture), confirm(client, token, capture))
    assert all(r.status_code == 200 for r in results)
    assert results[0].json()["transaction_ids"] == results[1].json()["transaction_ids"]
    assert len((await client.get('/transactions', headers=auth(token))).json()) == 1


@pytest.mark.asyncio
async def test_paired_transfer_creation_and_archive(client, provider):
    token = await register_and_login(client)
    await client.patch('/auth/me', headers=auth(token), json={"review_transactions": False})
    provider.extract_financial_event.return_value = completed(
        AITransaction(type="transfer", direction="debit", amount=500, account="Cash"),
        AITransaction(type="transfer", direction="credit", amount=500, account="Spending Account"))
    capture = (await post_capture(client, token, "Transfer 500 from Cash to Spending Account")).json()
    assert capture["status"] == "completed", capture
    ids = capture["transaction_ids"]
    provider.extract_financial_event.return_value = completed(AITransaction(operation="delete", transaction_id=UUID(ids[0])))
    unpaired = (await post_capture(client, token, "Archive one entry", capture["conversation_id"])).json()
    assert unpaired["status"] == "needs_clarification"
    assert len((await client.get('/transactions', headers=auth(token))).json()) == 2
    provider.extract_financial_event.return_value = completed(*[AITransaction(operation="delete", transaction_id=UUID(tid)) for tid in ids])
    paired = (await post_capture(client, token, "Archive both transfer entries", capture["conversation_id"])).json()
    assert paired["status"] == "completed", paired
    assert (await client.get('/transactions', headers=auth(token))).json() == []


@pytest.mark.asyncio
async def test_other_users_cannot_confirm_or_target_transactions(client, provider):
    token = await register_and_login(client)
    provider.extract_financial_event.return_value = completed(expense(200, description="Coffee"))
    capture = (await post_capture(client, token, "Spent 200 on coffee")).json()
    await client.post('/auth/register', json={"name": "Other", "email": "other@example.com", "password": "password123"})
    other = (await client.post('/auth/login', json={"email": "other@example.com", "password": "password123"})).json()["access_token"]
    assert (await confirm(client, other, capture)).status_code == 400
    tid = (await confirm(client, token, capture)).json()["transaction_ids"][0]
    await client.patch('/auth/me', headers=auth(other), json={"review_transactions": False})
    provider.extract_financial_event.return_value = completed(AITransaction(operation="delete", transaction_id=UUID(tid)))
    attack = (await post_capture(client, other, "Delete this transaction")).json()
    assert attack["status"] == "needs_clarification"
    assert (await confirm(client, other, attack)).status_code == 400
    assert (await client.get(f'/transactions/{tid}', headers=auth(token))).status_code == 200


@pytest.mark.asyncio
async def test_lending_clarification_does_not_become_expense(client, provider):
    token = await register_and_login(client)
    await client.post('/people', headers=auth(token), json={"name": "Farooq"})
    provider.extract_financial_event.return_value = CaptureAIResponse(status="needs_clarification", transactions=[AITransaction(type="lend", direction="debit", amount=350)], missing_fields=["person"], assistant_message="Who?", confidence=.9)
    first = (await post_capture(client, token, "Lent 350")).json()
    provider.extract_financial_event.return_value = completed(expense(500, person="Farooq"))
    second = (await post_capture(client, token, "Farooq", first["conversation_id"])).json()
    assert second["proposed_transactions"][0]["type"] == "lend"
    assert second["proposed_transactions"][0]["amount"] == "350"
    assert (await confirm(client, token, second)).status_code == 200


@pytest.mark.asyncio
async def test_resuming_proposal_can_replace_default_account_without_changing_amount(client, provider):
    token = await register_and_login(client)
    provider.extract_financial_event.return_value = completed(expense(219, description="Recharge"))
    first = (await post_capture(client, token, "Spent 219 on recharge")).json()
    provider.extract_financial_event.return_value = completed(expense(500, account="Cash", description="Recharge"), event_id=UUID(first["financial_event_id"]))
    second = (await post_capture(client, token, "Cash", first["conversation_id"])).json()
    assert second["proposed_transactions"][0]["account"] == "Cash"
    assert second["proposed_transactions"][0]["amount"] == "219"
    assert (await confirm(client, token, second)).status_code == 200
