import logging

from app.ai.gemini_provider import GeminiProvider
from app.ai.openai_provider import OpenAIProvider
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_ai_provider():
    provider_name = settings.AI_PROVIDER.strip().lower()
    logger.info(
        "Using AI provider=%s model=%s",
        provider_name,
        settings.OPENAI_MODEL if provider_name == "openai" else settings.GEMINI_MODEL,
    )

    if provider_name == "openai":
        return OpenAIProvider()

    if provider_name != "gemini":
        raise RuntimeError(f"Unsupported AI provider: {settings.AI_PROVIDER}")

    return GeminiProvider()
