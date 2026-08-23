from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts import repository as accounts_repository
from app.modules.categories import repository as categories_repository
from app.modules.people import repository as people_repository


async def build_capture_context(db: AsyncSession, user_id) -> dict:
    accounts = await accounts_repository.get_accounts(db, user_id)
    categories = await categories_repository.get_categories(db, user_id)
    people = await people_repository.get_people(db, user_id)

    return {
        "today": datetime.now(timezone.utc).date().isoformat(),
        "accounts": [a.name for a in accounts],
        "categories": [c.name for c in categories],
        "people": [p.name for p in people],
    }