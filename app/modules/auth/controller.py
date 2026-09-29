import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.database import get_db
from app.core.object_storage import (
    ObjectStorageNotConfigured,
    create_download_url,
    delete_object,
    upload_profile_image,
)
from app.modules.auth.schemas import RegisterRequest, RegisterResponse, LoginRequest, LoginResponse, UpdateProfileRequest
from app.modules.auth.service import register_user, login_user, logout_user, refresh_session, update_user_profile
from app.modules.auth import repository as auth_repository
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User


router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer_scheme = HTTPBearer()
logger = logging.getLogger(__name__)
MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024
AVATAR_FORMATS = {
    "image/jpeg": ("jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    "image/png": ("png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/webp": ("webp", lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"),
}


async def _avatar_url(user: User) -> str | None:
    if not user.avatar_key:
        return None
    try:
        return await run_in_threadpool(create_download_url, user.avatar_key)
    except Exception as exc:
        logger.exception("Unable to sign profile image URL")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Profile image storage is temporarily unavailable",
        ) from exc


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    try:
        user = await register_user(
            db=db,
            name=data.name,
            email=data.email,
            password=data.password,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Authentication failed"
        )

    return RegisterResponse(
        id=user.id,
        name=user.name,
        email=data.email,
        status=user.status,
        review_transactions=user.review_transactions,
        timezone=user.timezone,
        avatar_url=await _avatar_url(user),
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    try:
        user, session_token = await login_user(
            db=db,
            email=data.email,
            password=data.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

    return LoginResponse(
        id=user.id,
        name=user.name,
        email=data.email,
        status=user.status,
        access_token=session_token,
        review_transactions=user.review_transactions,
        timezone=user.timezone,
        avatar_url=await _avatar_url(user),
    )


@router.get("/me", response_model=RegisterResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RegisterResponse:
    identity = await auth_repository.get_identity_by_user_id(db, current_user.id)
    return RegisterResponse(
        id=current_user.id,
        name=current_user.name,
        email=identity.email if identity else None,
        status=current_user.status,
        review_transactions=current_user.review_transactions,
        timezone=current_user.timezone,
        avatar_url=await _avatar_url(current_user),
    )


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    await logout_user(db=db, token=credentials.credentials)

    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    try:
        user, token = await refresh_session(db=db, token=credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    identity = await auth_repository.get_identity_by_user_id(db, user.id)
    return LoginResponse(
        id=user.id,
        name=user.name,
        email=identity.email if identity else None,
        status=user.status,
        access_token=token,
        review_transactions=user.review_transactions,
        timezone=user.timezone,
        avatar_url=await _avatar_url(user),
    )


@router.patch("/me", response_model=RegisterResponse)
async def update_me(
    data: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RegisterResponse:
    try:
        user = await update_user_profile(db=db, user=current_user, **data.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    identity = await auth_repository.get_identity_by_user_id(db, user.id)
    return RegisterResponse(
        id=user.id,
        name=user.name,
        email=identity.email if identity else None,
        status=user.status,
        review_transactions=user.review_transactions,
        timezone=user.timezone,
        avatar_url=await _avatar_url(user),
    )


@router.post("/me/avatar", response_model=RegisterResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RegisterResponse:
    format_details = AVATAR_FORMATS.get(file.content_type or "")
    if not format_details:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Use a JPEG, PNG, or WebP image")

    content = await file.read(MAX_AVATAR_SIZE_BYTES + 1)
    await file.close()
    if len(content) > MAX_AVATAR_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Profile images must be 5 MB or smaller")

    extension, is_valid_image = format_details
    if not is_valid_image(content):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is not a valid supported image")

    try:
        new_key = await run_in_threadpool(
            upload_profile_image,
            str(current_user.id),
            content,
            file.content_type,
            extension,
        )
    except ObjectStorageNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unable to upload profile image")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Profile image upload failed") from exc

    old_key = current_user.avatar_key
    try:
        user = await update_user_profile(db, current_user, avatar_key=new_key)
    except Exception:
        try:
            await run_in_threadpool(delete_object, new_key)
        except Exception:
            logger.exception("Unable to clean up unlinked profile image")
        raise

    if old_key:
        try:
            await run_in_threadpool(delete_object, old_key)
        except Exception:
            logger.exception("Unable to remove replaced profile image")

    identity = await auth_repository.get_identity_by_user_id(db, user.id)
    return RegisterResponse(
        id=user.id,
        name=user.name,
        email=identity.email if identity else None,
        status=user.status,
        review_transactions=user.review_transactions,
        timezone=user.timezone,
        avatar_url=await _avatar_url(user),
    )


@router.delete("/me/avatar", response_model=RegisterResponse)
async def remove_avatar(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RegisterResponse:
    old_key = current_user.avatar_key
    if old_key:
        current_user.avatar_key = None
        await db.commit()
        await db.refresh(current_user)
        try:
            await run_in_threadpool(delete_object, old_key)
        except Exception:
            logger.exception("Unable to remove profile image from object storage")

    identity = await auth_repository.get_identity_by_user_id(db, current_user.id)
    return RegisterResponse(
        id=current_user.id,
        name=current_user.name,
        email=identity.email if identity else None,
        status=current_user.status,
        review_transactions=current_user.review_transactions,
        timezone=current_user.timezone,
        avatar_url=None,
    )
