from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.schemas import RegisterRequest, RegisterResponse, LoginRequest, LoginResponse, UpdateProfileRequest
from app.modules.auth.service import register_user, login_user, logout_user, refresh_session, update_user_profile
from app.modules.auth import repository as auth_repository
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User


router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer_scheme = HTTPBearer()


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
    return RegisterResponse(id=user.id, name=user.name, email=identity.email if identity else None, status=user.status, review_transactions=user.review_transactions, timezone=user.timezone)
