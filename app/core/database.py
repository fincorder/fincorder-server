from collections.abc import AsyncGenerator
from uuid import uuid4

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.pool import NullPool

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def create_database_engine(database_url: str, *, echo: bool = False):
    engine_options = {}
    if settings.uses_pooled_database:
        engine_options = {
            "poolclass": NullPool,
            "connect_args": {"prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__"},
        }
    return create_async_engine(database_url, echo=echo, **engine_options)


engine = create_database_engine(settings.database_url, echo=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
