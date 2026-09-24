from abc import ABC, abstractmethod
import json

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
            f"Default account when the user does not specify one: {context.get('default_account') or 'None'}\n"
            f"Categories: {', '.join(context['categories']) or 'None'}\n"
            f"People: {', '.join(context['people']) or 'None'}"
        )

        if context.get("transactions"):
            result += "\nRecent transactions (use the exact id for edits or deletions):\n"
            for transaction in context["transactions"]:
                result += (
                    f"{transaction['id']} | {transaction['type']} | "
                    f"{transaction.get('direction', '')} | group={transaction.get('transaction_group_id', '')} | "
                    f"{transaction['amount']} {transaction['currency']} | "
                    f"{transaction['account']} | {transaction['category']} | "
                    f"{transaction['person']} | {transaction['description']} | "
                    f"{transaction['transaction_date']}\n"
                )

        if context["messages"]:
            result += "\nConversation:\n"

            for message in context["messages"]:
                result += f"{message['role']}: {message['content']}\n"

        if context.get("pending_event"):
            pending_event = context["pending_event"]
            result += (
                "\nPending clarification event (authoritative known facts):\n"
                f"Original message: {pending_event['raw_text']}\n"
                f"Known extracted data: {pending_event['extracted_data']}\n"
                f"Locked amount: {(pending_event['extracted_data'] or {}).get('locked_amount', 'none')}\n"
                f"Still missing: {', '.join(pending_event['missing_fields']) or 'none'}\n"
                "Preserve these known facts, especially the locked amount, unless the current user message explicitly corrects them.\n"
            )

        if context.get("pending_events"):
            result += "\nUnfinished drafts (select continuation_event_id only when the user continues one):\n" + json.dumps(context["pending_events"], default=str)

        return result
