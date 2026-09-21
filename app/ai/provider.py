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

    def format_context(self, context: dict) -> str:
        result = (
            f"Today: {context['today']}\n"
            f"Accounts: {', '.join(context['accounts']) or 'None'}\n"
            f"Categories: {', '.join(context['categories']) or 'None'}\n"
            f"People: {', '.join(context['people']) or 'None'}"
        )

        if context.get("transactions"):
            result += "\nRecent transactions (use the exact id for edits or deletions):\n"
            for transaction in context["transactions"]:
                result += (
                    f"{transaction['id']} | {transaction['type']} | "
                    f"{transaction['amount']} {transaction['currency']} | "
                    f"{transaction['account']} | {transaction['category']} | "
                    f"{transaction['person']} | {transaction['description']} | "
                    f"{transaction['transaction_date']}\n"
                )

        if context["messages"]:
            result += "\nConversation:\n"

            for message in context["messages"]:
                result += f"{message['role']}: {message['content']}\n"

        return result
