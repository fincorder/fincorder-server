from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import AIProvider
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.capture.dependencies import get_ai_provider
from app.modules.capture.schemas import CaptureRequest, CaptureResponse
from app.modules.capture.service import capture_message
from app.modules.users.models import User

router = APIRouter(prefix="/capture", tags=["Capture"])


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