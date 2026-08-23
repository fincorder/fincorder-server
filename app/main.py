from fastapi import FastAPI

from app.modules.auth.controller import router as auth_router
from app.modules.accounts.controller import router as accounts_router
from app.modules.categories.controller import router as categories_router
from app.modules.people.controller import router as people_router
from app.modules.conversations.controller import router as conversations_router
from app.modules.messages.controller import router as messages_router
from app.modules.financial_events.controller import router as financial_events_router
from app.modules.transaction_groups.controller import router as transaction_groups_router
from app.modules.transactions.controller import router as transactions_router
from app.modules.capture.controller import router as capture_router


app = FastAPI()

@app.get("/")
async def root():
    return {
        "status": "ok"
    }

app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(categories_router)
app.include_router(people_router)
app.include_router(conversations_router)
app.include_router(messages_router)
app.include_router(financial_events_router)
app.include_router(transaction_groups_router)
app.include_router(transactions_router)
app.include_router(capture_router)