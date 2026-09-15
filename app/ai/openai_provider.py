import json
from openai import AsyncOpenAI

from app.ai.prompts import CAPTURE_EXAMPLES, CAPTURE_SYSTEM_PROMPT
from app.ai.provider import AIProvider
from app.ai.schemas import CaptureAIResponse
from app.core.config import settings


class OpenAIProvider(AIProvider):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL

    async def extract_financial_event(self, message: str, context: dict | None = None) -> CaptureAIResponse:
        input_messages = []
        if context:
            input_messages.append({ "role": "developer", "content": self.format_context(context) })

        for example in CAPTURE_EXAMPLES:
            input_messages.extend(
                [
                    {"role": "user", "content": example["user"]},
                    {"role": "assistant", "content": json.dumps(example["assistant"], ensure_ascii=False)},
                ]
            )

        input_messages.append({"role": "user", "content": message})

        response = await self.client.responses.parse(
            model=self.model,
            instructions=CAPTURE_SYSTEM_PROMPT,
            input=input_messages,
            text_format=CaptureAIResponse,
            reasoning={"effort": "low"},
            max_output_tokens=4096,
        )

        return self.parse_output(response)


    def parse_output(self, response) -> CaptureAIResponse:
        if response.output_parsed is not None:
            return response.output_parsed

        if response.output_text:
            return CaptureAIResponse.model_validate_json(response.output_text)

        return CaptureAIResponse(
            status="failed",
            assistant_message="I couldn't extract a financial event from that message.",
            confidence=0.0,
        )