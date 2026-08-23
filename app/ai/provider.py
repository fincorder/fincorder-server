from abc import ABC, abstractmethod

from app.ai.schemas import CaptureAIResponse


class AIProvider(ABC):
    @abstractmethod
    async def extract_financial_event(self, message: str, context: dict | None = None) -> CaptureAIResponse:
        """
        Convert a user's natural-language financial message into
        structured financial data.
        """
        pass