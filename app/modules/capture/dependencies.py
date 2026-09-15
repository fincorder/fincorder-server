from app.ai.gemini_provider import GeminiProvider
from app.ai.openai_provider import OpenAIProvider
from app.core.config import settings

def get_ai_provider():
    if settings.AI_PROVIDER == "openai":
        return OpenAIProvider()

    return GeminiProvider()