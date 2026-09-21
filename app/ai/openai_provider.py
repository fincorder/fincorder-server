import json
import logging
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.ai.prompts import CAPTURE_EXAMPLES, CAPTURE_SYSTEM_PROMPT
from app.ai.provider import AIProvider
from app.ai.schemas import CaptureAIResponse
from app.core.config import settings

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not configured")

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

        try:
            response = await self.client.responses.parse(
                model=self.model,
                instructions=CAPTURE_SYSTEM_PROMPT,
                input=input_messages,
                text_format=CaptureAIResponse,
                max_output_tokens=4096,
            )
        except ValidationError:
            logger.exception("OpenAI returned an invalid or empty structured capture response model=%s", self.model)
            return CaptureAIResponse(
                status="failed",
                assistant_message="I couldn't process the transaction because the AI service returned an invalid response. Please try again.",
                confidence=0.0,
            )
        except Exception:
            logger.exception("OpenAI capture extraction failed model=%s", self.model)
            raise

        return self.parse_output(response)


    def parse_output(self, response) -> CaptureAIResponse:
        parsed_output = getattr(response, "output_parsed", None)
        if parsed_output is not None:
            try:
                if isinstance(parsed_output, CaptureAIResponse):
                    return parsed_output
                return CaptureAIResponse.model_validate(parsed_output)
            except ValidationError:
                logger.exception("OpenAI returned invalid structured capture output model=%s", self.model)

        output_text = (getattr(response, "output_text", "") or "").strip()
        if output_text:
            try:
                return CaptureAIResponse.model_validate_json(output_text)
            except ValidationError:
                logger.exception("OpenAI returned invalid JSON capture output model=%s", self.model)

        logger.warning(
            "OpenAI returned no usable capture output model=%s status=%s incomplete_details=%s",
            self.model,
            getattr(response, "status", None),
            getattr(response, "incomplete_details", None),
        )

        return CaptureAIResponse(
            status="failed",
            assistant_message="I couldn't extract a financial event from that message.",
            confidence=0.0,
        )
