from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.messages.models import Message


async def create_message(db: AsyncSession, message: Message) -> Message:
    db.add(message)
    await db.flush()
    return message


async def get_messages(db: AsyncSession, conversation_id) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )

    return list(result.scalars().all())


async def get_message_by_id(db: AsyncSession, message_id) -> Message | None:
    result = await db.execute(
        select(Message).where(Message.id == message_id)
    )

    return result.scalar_one_or_none()