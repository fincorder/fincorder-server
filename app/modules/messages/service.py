import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.conversations import repository as conversations_repository
from app.modules.messages import repository
from app.modules.messages.models import Message, MessageRole


async def create_message(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID, role: MessageRole, content: str) -> Message:
    conversation = await conversations_repository.get_conversation_by_id(db, conversation_id, user_id)
    if not conversation:
        raise ValueError("Conversation not found")

    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
    )

    await repository.create_message(db, message)
    await db.commit()

    return message


async def get_messages(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> list[Message]:
    conversation = await conversations_repository.get_conversation_by_id(db, conversation_id, user_id)
    if not conversation:
        raise ValueError("Conversation not found")

    return await repository.get_messages(db, conversation_id)


async def get_message(db: AsyncSession, message_id: uuid.UUID, user_id: uuid.UUID) -> Message:
    message = await repository.get_message_by_id(db, message_id)
    if not message:
        raise ValueError("Message not found")
    
    conversation = await conversations_repository.get_conversation_by_id(
        db,
        message.conversation_id,
        user_id,
    )
    if not conversation:
        raise ValueError("Message not found")

    return message