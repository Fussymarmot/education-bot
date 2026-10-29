from aiogram import Router

from handlers import admin, reactions, users


def setup_routers() -> Router:
    """users - the work group, reactions - emoji reactions in the group, admin - administrator DMs. Everything else is ignored."""
    root = Router(name="root")
    root.include_router(users.router)
    root.include_router(reactions.router)  # после users: команды не должны попадать сюда
    root.include_router(admin.router)
    return root
