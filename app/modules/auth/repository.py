import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.auth.models import UserIdentity
from app.modules.auth.models import Session


async def get_identity_by_email(db: AsyncSession, email: str) -> UserIdentity | None:
    """Fetch user identity by email and password provider"""
    result = await db.execute(
        select(UserIdentity).where(
            UserIdentity.email == email,
            UserIdentity.provider == "password",
        )
    )
    return result.scalar_one_or_none()


async def get_identity_by_user_id(db: AsyncSession, user_id: uuid.UUID) -> UserIdentity | None:
    """Fetch the primary identity for a user."""
    result = await db.execute(
        select(UserIdentity)
        .where(UserIdentity.user_id == user_id)
        .order_by(UserIdentity.created_at)
    )
    return result.scalars().first()


async def create_user(db: AsyncSession, user: User) -> User:
    """Create new user"""
    db.add(user)
    await db.flush()
    return user


async def create_identity(db: AsyncSession, identity: UserIdentity) -> UserIdentity:
    """Create new identity"""
    db.add(identity)
    await db.flush()
    return identity


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Fetch user by ID"""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_session(db: AsyncSession, session: Session) -> Session:
    "Create user login session"
    db.add(session)
    await db.flush()
    return session


async def get_active_session_by_token_hash(db: AsyncSession, token_hash: str) -> Session | None:
    "Fetch active session of user"
    result = await db.execute(
        select(Session).where(
            Session.token_hash == token_hash,
            Session.revoked_at.is_(None),
            Session.expires_at > datetime.now(timezone.utc),
        )
    )
    return result.scalar_one_or_none()


async def revoke_session(db: AsyncSession, session: Session) -> None:
    "Revoke user login session"
    session.revoked_at = datetime.now(timezone.utc)
    await db.flush()


async def delete_session(db: AsyncSession, session: Session) -> None:
    "Delete expired session"
    await db.delete(session)
    await db.flush()
