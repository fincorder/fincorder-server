from fastapi import FastAPI

from app.modules.auth.controller import router as auth_router
from app.modules.accounts.controller import router as accounts_router
from app.modules.categories.controller import router as categories_router
from app.modules.people.controller import router as people_router


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