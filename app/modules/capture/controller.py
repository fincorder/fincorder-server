import logging

from fastapi import APIRouter, Depends, HTTPException, status
from openai import APIConnectionError, OpenAIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import AIProvider
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.capture.dependencies import get_ai_provider
from app.modules.capture.schemas import CaptureRequest, CaptureResponse
from app.modules.capture.service import capture_message
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
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
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
        logger.exception(
            "Capture request failed conversation_id=%s",
            data.conversation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Capture could not be completed. Check the backend logs for details.",
        ) from exc
