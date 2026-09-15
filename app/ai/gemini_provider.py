import json
from google import genai
from google.genai import types

from app.ai.prompts import CAPTURE_EXAMPLES, CAPTURE_SYSTEM_PROMPT
from app.ai.provider import AIProvider
from app.ai.schemas import CaptureAIResponse
from app.core.config import settings


class GeminiProvider(AIProvider):
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_MODEL

    async def extract_financial_event(self, message: str, context: dict | None = None) -> CaptureAIResponse:
        contents = []

        if context:
            contents.append({
                "role": "user",
                "parts": [{"text": self.format_context(context)}],
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood."}],
            })

        for example in CAPTURE_EXAMPLES:
            contents.extend(
                [
                    {"role": "user", "parts": [{"text": example["user"]}]},
                    {"role": "model", "parts": [{"text": json.dumps(example["assistant"], ensure_ascii=False)}]},
                ]
            )

        contents.append({"role": "user", "parts": [{"text": message}]})

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=CAPTURE_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_json_schema=CaptureAIResponse.model_json_schema(),
            ),
        )

        return self.parse_output(response)


    def parse_output(self, response) -> CaptureAIResponse:
        if response.parsed is not None:
            if isinstance(response.parsed, CaptureAIResponse):
                return response.parsed

            return CaptureAIResponse.model_validate(response.parsed)

        if response.text:
            return CaptureAIResponse.model_validate_json(response.text)

        return CaptureAIResponse(
            status="failed",
            assistant_message="I couldn't extract a financial event from that message.",
            confidence=0.0,
        )