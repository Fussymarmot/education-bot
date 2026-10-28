from aiogram import Router

from handlers import admin, users


def setup_routers() -> Router:
    """users - the work group, admin - administrator DMs. Everything else is ignored."""
    root = Router(name="root")
    root.include_router(users.router)
    root.include_router(admin.router)
    return root
