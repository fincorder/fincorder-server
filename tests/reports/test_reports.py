from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from app.modules.conversations.models import Conversation
from app.modules.financial_events.models import FinancialEvent, FinancialEventStatus
from app.modules.messages.models import Message, MessageRole
from app.modules.transaction_groups.models import TransactionGroup, TransactionGroupStatus
from app.modules.transactions.models import Transaction, TransactionDirection, TransactionType


async def register(client, email):
    await client.post('/auth/register', json={'name': 'Report User', 'email': email, 'password': 'password123'})
    login = await client.post('/auth/login', json={'email': email, 'password': 'password123'})
    return {'Authorization': f"Bearer {login.json()['access_token']}"}


async def add_group(db, user_id):
    conversation = Conversation(user_id=user_id, title='Report fixtures')
    db.add(conversation)
    await db.flush()
    message = Message(conversation_id=conversation.id, role=MessageRole.SYSTEM, content='Fixture')
    db.add(message)
    await db.flush()
    event = FinancialEvent(conversation_id=conversation.id, source_message_id=message.id, status=FinancialEventStatus.COMPLETED, raw_text='Fixture')
    db.add(event)
    await db.flush()
    group = TransactionGroup(financial_event_id=event.id, status=TransactionGroupStatus.POSTED)
    db.add(group)
    await db.flush()
    return group.id


@pytest.mark.asyncio
async def test_reports_exclude_deleted_and_pair_transfers_once(client, db_session):
    headers = await register(client, 'reports@example.com')
    user_id = UUID((await client.get('/auth/me', headers=headers)).json()['id'])
    accounts = (await client.get('/accounts', headers=headers)).json()
    source = UUID(accounts[0]['id'])
    target = UUID((await client.post('/accounts', headers=headers, json={'name': 'Savings', 'currency': 'INR'},)).json()['id'])
    person = UUID((await client.post('/people', headers=headers, json={'name': 'Farooq'})).json()['id'])
    when = datetime(2026, 9, 12, 12, tzinfo=timezone.utc)
    group = await add_group(db_session, user_id)

    def tx(kind, direction, amount, *, account=source, person_id=None, deleted=False, description='Entry'):
        db_session.add(Transaction(transaction_group_id=group, user_id=user_id, account_id=account, person_id=person_id, type=kind, direction=direction, amount=Decimal(amount), currency='INR', description=description, transaction_date=when, deleted_at=when if deleted else None))

    tx(TransactionType.EXPENSE, TransactionDirection.DEBIT, '200', description='Coffee')
    tx(TransactionType.EXPENSE, TransactionDirection.DEBIT, '900', deleted=True)
    tx(TransactionType.INCOME, TransactionDirection.CREDIT, '1000')
    tx(TransactionType.LEND, TransactionDirection.DEBIT, '350', person_id=person)
    tx(TransactionType.REPAYMENT, TransactionDirection.CREDIT, '100', person_id=person)
    tx(TransactionType.TRANSFER, TransactionDirection.DEBIT, '500', account=source)
    tx(TransactionType.TRANSFER, TransactionDirection.CREDIT, '500', account=target)
    reversed_group = await add_group(db_session, user_id)
    reversed = await db_session.get(TransactionGroup, reversed_group)
    reversed.status = TransactionGroupStatus.REVERSED
    db_session.add(Transaction(transaction_group_id=reversed_group, user_id=user_id, account_id=source, type=TransactionType.EXPENSE, direction=TransactionDirection.DEBIT, amount=Decimal('700'), currency='INR', description='Reversed', transaction_date=when))
    await db_session.commit()

    params = {'date_from': '2026-09-01', 'date_to': '2026-09-30', 'currency': 'INR'}
    overview = await client.get('/reports/overview', headers=headers, params=params)
    assert overview.status_code == 200, overview.text
    assert overview.json()['metrics']['spending'] == '200.00'
    assert overview.json()['metrics']['income'] == '1000.00'
    assert overview.json()['metrics']['transfer_volume'] == '500.00'
    assert overview.json()['metrics']['transactions'] == 5
    assert overview.json()['metrics']['spending_change'] == '200.00'
    assert overview.json()['comparison']['date_to'] == '2026-08-31'

    transfers = await client.get('/reports/transfers', headers=headers, params=params)
    assert transfers.json()['total'] == 1
    assert transfers.json()['rows'][0]['from_account_id'] == str(source)
    assert transfers.json()['rows'][0]['to_account_id'] == str(target)

    account_report = await client.get('/reports/accounts', headers=headers, params=params)
    assert account_report.status_code == 200
    assert any(row['key'] == str(target) and row['transfer_volume'] == '500.00' for row in account_report.json()['rows'])

    for view in ('spending', 'income', 'categories', 'activity', 'types', 'quality', 'pivot'):
        response = await client.get(f'/reports/{view}', headers=headers, params=params)
        assert response.status_code == 200, (view, response.text)
        assert response.json()['report'] == view
        if view == 'types':
            transfer_row = next(row for row in response.json()['rows'] if row['key'] == 'transfer')
            assert transfer_row['count'] == 1
            assert transfer_row['amount'] == '500.00'

    options = await client.get('/reports/options', headers=headers)
    assert options.status_code == 200
    assert any(option['id'] == str(target) for option in options.json()['accounts'])

    people = await client.get('/reports/people', headers=headers, params={**params, 'date_from': '2026-09-13'})
    assert people.status_code == 200, people.text
    assert people.json()['metrics']['owed_to_you'] == '250.00'
    assert people.json()['metrics']['lent'] == '0.00'

    isolated = await register(client, 'other-reports@example.com')
    assert (await client.get('/reports/overview', headers=isolated, params=params)).json()['metrics']['spending'] == '0.00'

    export = await client.get('/reports/export', headers=headers, params={**params, 'view': 'transfers'})
    assert export.status_code == 200
    assert 'Savings' in export.text

    paged = await client.get('/reports/activity', headers=headers, params={**params, 'limit': 1})
    assert paged.json()['total'] == 6
    assert paged.json()['has_next'] is True


@pytest.mark.asyncio
async def test_pivot_and_invalid_range(client):
    headers = await register(client, 'pivot@example.com')
    response = await client.get('/reports/pivot', headers=headers, params={'pivot_row': 'category', 'pivot_column': 'month'})
    assert response.status_code == 200
    assert response.json()['pivot_columns'] == []
    invalid = await client.get('/reports/overview', headers=headers, params={'date_from': '2026-10-01', 'date_to': '2026-09-01'})
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_report_dates_use_user_timezone_and_keep_currencies_separate(client, db_session):
    headers = await register(client, 'timezone-reports@example.com')
    await client.patch('/auth/me', headers=headers, json={'timezone': 'Asia/Kolkata'})
    user_id = UUID((await client.get('/auth/me', headers=headers)).json()['id'])
    account_id = UUID((await client.get('/accounts', headers=headers)).json()[0]['id'])
    group = await add_group(db_session, user_id)
    for currency, amount in (('INR', '219'), ('USD', '15')):
        db_session.add(Transaction(transaction_group_id=group, user_id=user_id, account_id=account_id, type=TransactionType.EXPENSE, direction=TransactionDirection.DEBIT, amount=Decimal(amount), currency=currency, description='Late-night payment', transaction_date=datetime(2026, 8, 31, 20, tzinfo=timezone.utc)))
    await db_session.commit()

    september = {'date_from': '2026-09-01', 'date_to': '2026-09-30'}
    inr = await client.get('/reports/overview', headers=headers, params={**september, 'currency': 'INR'})
    usd = await client.get('/reports/overview', headers=headers, params={**september, 'currency': 'USD'})
    assert inr.json()['metrics']['spending'] == '219.00'
    assert usd.json()['metrics']['spending'] == '15.00'
    august = await client.get('/reports/overview', headers=headers, params={'date_from': '2026-08-01', 'date_to': '2026-08-31'})
    assert august.json()['metrics']['spending'] == '0.00'


def test_csv_export_escapes_formula_content():
    from app.modules.reports.export import report_csv

    csv = report_csv({'report': 'activity', 'rows': [{'description': '=HYPERLINK("bad")', 'amount': '-10.00'}]})
    assert "'=HYPERLINK" in csv
    assert "-10.00" in csv
