import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from openai import APIConnectionError, OpenAIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import AIProvider
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.capture.dependencies import get_ai_provider
from app.modules.capture.schemas import (
    CaptureRequest,
    CaptureResponse,
    ConfirmCaptureRequest,
    ConfirmCaptureResponse,
)
from app.modules.capture.service import capture_message, confirm_capture, reject_capture, save_capture_draft
from app.modules.users.models import User

router = APIRouter(prefix="/capture", tags=["Capture"])
logger = logging.getLogger(__name__)


@router.post("", response_model=CaptureResponse)
async def capture_controller(
    data: CaptureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai_provider: AIProvider = Depends(get_ai_provider),
):
    try:
        return await capture_message(
            db=db,
            user=current_user,
            message=data.message,
            conversation_id=data.conversation_id,
            ai_provider=ai_provider,
            request_id=data.request_id,
            financial_event_id=data.financial_event_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except APIConnectionError as exc:
        logger.exception("AI provider connection failed during capture")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI provider is unreachable. Check the backend network or proxy configuration.",
        ) from exc
    except OpenAIError as exc:
        logger.exception("AI provider request failed during capture")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI provider rejected the capture request.",
        ) from exc
    except Exception as exc:
        logger.exception("Capture request failed conversation_id=%s", data.conversation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Capture could not be completed. Check the backend logs for details.",
        ) from exc


@router.post("/{financial_event_id}/confirm", response_model=ConfirmCaptureResponse)
async def confirm_capture_controller(
    financial_event_id: uuid.UUID,
    data: ConfirmCaptureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await confirm_capture(
            db=db,
            financial_event_id=financial_event_id,
            user=current_user,
            transactions=data.transactions,
            revision=data.revision,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{financial_event_id}/reject", response_model=ConfirmCaptureResponse)
async def reject_capture_controller(
    financial_event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await reject_capture(
            db=db,
            financial_event_id=financial_event_id,
            user=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{financial_event_id}/draft", response_model=ConfirmCaptureResponse)
async def save_capture_draft_controller(
    financial_event_id: uuid.UUID,
    data: ConfirmCaptureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await save_capture_draft(db, financial_event_id, current_user, data.transactions, data.revision)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
