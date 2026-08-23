from app.ai.provider import AIProvider
from app.ai.schemas import AITransaction, CaptureAIResponse


class MockAIProvider(AIProvider):
    async def extract_financial_event(self, message, context=None):
        if message == "Paid ₹500":
            return CaptureAIResponse(
                status="needs_clarification",
                transactions=[],
                missing_fields=["category"],
                assistant_message="What was the ₹500 for?",
                confidence=0.9,
            )

        return CaptureAIResponse(
            status="completed",
            transactions=[
                AITransaction(
                    type="expense",
                    amount=500,
                    currency="INR",
                    account="Spending Account",
                    category="Transport",
                    person=None,
                    description="Petrol",
                    transaction_date=None,
                    direction="debit",
                )
            ],
            missing_fields=[],
            assistant_message="Recorded your ₹500 petrol expense.",
            confidence=0.99,
        )