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
        )

        return response.output_parsed


    def format_context(self, context: dict) -> str:
        result = (
            f"Today: {context['today']}\n"
            f"Accounts: {', '.join(context['accounts']) or 'None'}\n"
            f"Categories: {', '.join(context['categories']) or 'None'}\n"
            f"People: {', '.join(context['people']) or 'None'}"
        )

        if context["messages"]:
            result += "\nConversation:\n"

            for message in context["messages"]:
                result += f"{message['role']}: {message['content']}\n"

        return result