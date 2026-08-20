from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.conversations.models import Conversation, ConversationStatus


async def create_conversation(db: AsyncSession, conversation: Conversation,) -> Conversation:
    """Create conversation session group"""
    db.add(conversation)
    await db.flush()
    return conversation


async def get_conversation_by_id(db: AsyncSession, conversation_id, user_id) -> Conversation | None:
    """Get entire conversation by ID"""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )

    return result.scalar_one_or_none()


async def get_conversations(db: AsyncSession, user_id) -> list[Conversation]:
    """Get list of conversations of a user"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    )

    return list(result.scalars().all())


async def update_conversation(db: AsyncSession, conversation: Conversation) -> Conversation:
    """Update conversation meta"""
    await db.flush()
    return conversation


async def archive_conversation(db: AsyncSession, conversation: Conversation) -> Conversation:
    """Archive / external soft delete conversation"""
    conversation.status = ConversationStatus.ARCHIVED
    await db.flush()
    return conversation