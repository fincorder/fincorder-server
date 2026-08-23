from app.modules.accounts import repository as accounts_repository
from app.modules.categories import repository as categories_repository
from app.modules.people import repository as people_repository


async def resolve_account_id(db, user_id, name):
    if not name:
        return None

    accounts = await accounts_repository.get_accounts(db, user_id)

    for account in accounts:
        if account.name.lower() == name.lower():
            return account.id

    raise ValueError(f"Account '{name}' not found")


async def resolve_category_id(db, user_id, name):
    if not name:
        return None

    categories = await categories_repository.get_categories(db, user_id)

    for category in categories:
        if category.name.lower() == name.lower():
            return category.id

    return None


async def resolve_person_id(db, user_id, name):
    if not name:
        return None

    people = await people_repository.get_people(db, user_id)

    for person in people:
        if person.name.lower() == name.lower():
            return person.id

    return None