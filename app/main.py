import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import configure_logging
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
from app.modules.reports.controller import router as reports_router


configure_logging()
app = FastAPI()
logger = logging.getLogger(__name__)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled request error method=%s path=%s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check the backend logs for details."},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(reports_router)
