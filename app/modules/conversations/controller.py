import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.conversations.schemas import ConversationResponse, CreateConversationRequest, UpdateConversationRequest
from app.modules.conversations.service import archive_conversation, create_conversation, get_conversation, get_conversations, update_conversation
from app.modules.users.models import User

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation_controller(
    data: CreateConversationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_conversation(
        db=db,
        user_id=current_user.id,
        title=data.title,
    )


@router.get("", response_model=list[ConversationResponse])
async def get_conversations_controller(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_conversations(db, current_user.id)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation_controller(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await get_conversation(
            db,
            conversation_id,
            current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation_controller(
    conversation_id: uuid.UUID,
    data: UpdateConversationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await update_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
            title=data.title,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.patch("/{conversation_id}/archive", response_model=ConversationResponse)
async def archive_conversation_controller(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await archive_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )