import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.conversations import repository
from app.modules.conversations.models import Conversation


async def create_conversation(db: AsyncSession, user_id: uuid.UUID, title: str | None = None) -> Conversation:
    conversation = Conversation(user_id=user_id, title=title)

    await repository.create_conversation(db, conversation)
    await db.commit()

    return conversation


async def get_conversations(db: AsyncSession, user_id: uuid.UUID) -> list[Conversation]:
    return await repository.get_conversations(db, user_id)


async def get_conversation(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
    conversation = await repository.get_conversation_by_id(db, conversation_id, user_id)
    if not conversation:
        raise ValueError("Conversation not found")

    return conversation


async def update_conversation(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID, title: str | None = None) -> Conversation:
    conversation = await repository.get_conversation_by_id(db, conversation_id, user_id)
    if not conversation:
        raise ValueError("Conversation not found")
    if title is not None:
        conversation.title = title

    await repository.update_conversation(db, conversation)
    await db.commit()

    return conversation


async def archive_conversation(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
    conversation = await repository.get_conversation_by_id(db, conversation_id, user_id)
    if not conversation:
        raise ValueError("Conversation not found")

    await repository.archive_conversation(db, conversation)
    await db.commit()

    return conversation