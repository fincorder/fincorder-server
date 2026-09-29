import asyncio

from alembic import context
from app.core.config import settings
from app.core.database import Base, create_database_engine

from app.modules.users.models import User
from app.modules.auth.models import UserIdentity, Session
from app.modules.accounts.models import Account
from app.modules.categories.models import Category
from app.modules.people.models import Person
from app.modules.conversations.models import Conversation
from app.modules.messages.models import Message
from app.modules.financial_events.models import FinancialEvent
from app.modules.transaction_groups.models import TransactionGroup
from app.modules.transactions.models import Transaction
from app.modules.capture.models import CaptureReceipt

config = context.config

config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_database_engine(settings.database_url)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
