from fastapi import FastAPI

from app.modules.auth.controller import router as auth_router

app = FastAPI()

@app.get("/")
async def root():
    return {
        "status": "ok"
    }

app.include_router(auth_router)