from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.schemas import RegisterRequest, RegisterResponse, LoginRequest, LoginResponse
from app.modules.auth.service import register_user, login_user, logout_user, refresh_session
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
        status=user.status,
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
        status=user.status,
        access_token=session_token,
    )


@router.get("/me", response_model=RegisterResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> RegisterResponse:
    return RegisterResponse(
        id=current_user.id,
        name=current_user.name,
        status=current_user.status,
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

    return LoginResponse(
        id=user.id,
        name=user.name,
        status=user.status,
        access_token=token,
    )