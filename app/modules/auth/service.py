import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from pwdlib import PasswordHash

from app.core.security import generate_session_token, hash_session_token, hash_password, verify_password

from app.modules.auth import repository
from app.modules.auth.models import UserIdentity, Session
from app.modules.users.models import User


async def register_user(db: AsyncSession, name: str, email: str, password: str) -> User:
    "Register a new user and identity"
    existing_identity = await repository.get_identity_by_email(db, email)

    if existing_identity:
        raise ValueError("Email already registered")

    user = User(
        id=uuid.uuid4(),
        name=name,
        status="active",
    )

    identity = UserIdentity(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="password",
        email=email,
        password_hash=hash_password(password),
        is_verified=False,
    )

    try:
        await repository.create_user(db, user)
        await repository.create_identity(db, identity)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return user


async def login_user(db: AsyncSession, email: str, password: str) -> User:
    "Verify existing user and create login session"
    identity = await repository.get_identity_by_email(db, email)

    if not identity or not identity.password_hash:
        raise ValueError("Invalid email or password")

    if not verify_password(password, identity.password_hash):
        raise ValueError("Invalid email or password")

    user = await repository.get_user_by_id(db, identity.user_id)

    if not user or user.status != "active":
        raise ValueError("Invalid email or password")

    session_token = generate_session_token()

    session = Session(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=hash_session_token(session_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        last_used_at=datetime.now(timezone.utc),
    )

    await repository.create_session(db, session)
    await db.commit()

    return user, session_token


async def logout_user(db: AsyncSession, token: str) -> None:
    "Logout user and revoke session"
    token_hash = hash_session_token(token)
    session = await repository.get_active_session_by_token_hash(db, token_hash)

    if session:
        await repository.revoke_session(db, session)
        await db.commit()


async def refresh_session(db: AsyncSession, token: str) -> tuple[User, str]:
    token_hash = hash_session_token(token)
    session = await repository.get_active_session_by_token_hash(db, token_hash)

    if not session:
        raise ValueError("Invalid or expired session")

    user = await repository.get_user_by_id(db, session.user_id)

    if not user or user.status != "active":
        raise ValueError("Invalid or inactive user")

    await repository.revoke_session(db, session)

    new_token = generate_session_token()

    new_session = Session(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=hash_session_token(new_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        created_at=datetime.now(timezone.utc),
        last_used_at=datetime.now(timezone.utc),
    )

    await repository.create_session(db, new_session)
    await db.commit()

    return user, new_token