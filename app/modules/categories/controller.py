import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.categories.schemas import CategoryResponse, CreateCategoryRequest, UpdateCategoryRequest
from app.modules.categories.service import create_category, delete_category, get_category, get_categories, update_category
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User


router = APIRouter(prefix="/categories", tags=["Categories"])


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category_controller(
    data: CreateCategoryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        category = await create_category(
            db=db,
            user_id=current_user.id,
            name=data.name,
            type=data.type,
        )
        return category
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.get("", response_model=list[CategoryResponse])
async def get_categories_controller(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_categories(db, current_user.id)


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category_controller(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await get_category(db, category_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category_controller(
    category_id: uuid.UUID,
    data: UpdateCategoryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await update_category(
            db=db,
            category_id=category_id,
            user_id=current_user.id,
            name=data.name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category_controller(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await delete_category(db, category_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )