import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.people.schemas import CreatePersonRequest, PersonResponse, UpdatePersonRequest
from app.modules.people.service import create_person, delete_person, get_people, get_person, update_person
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User


router = APIRouter(prefix="/people", tags=["People"])


@router.post("", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
async def create_person_controller(
    data: CreatePersonRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        person = await create_person(
            db=db,
            user_id=current_user.id,
            name=data.name,
        )
        return person
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.get("", response_model=list[PersonResponse])
async def get_people_controller(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_people(db, current_user.id)


@router.get("/{person_id}", response_model=PersonResponse)
async def get_person_controller(
    person_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await get_person(db, person_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.patch("/{person_id}", response_model=PersonResponse)
async def update_person_controller(
    person_id: uuid.UUID,
    data: UpdatePersonRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await update_person(
            db=db,
            person_id=person_id,
            user_id=current_user.id,
            name=data.name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person_controller(
    person_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await delete_person(db, person_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
