"""Bot entry point. Run with: python main.py"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database import close_db, init_db
from handlers import setup_routers
from utils.common.commands import setup_commands
from utils.replacements.replacements_service import poller

log = logging.getLogger("bot")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.bot_token:
        raise SystemExit("BOT_TOKEN not set: configure it in environment variables or .env file")
    if not config.admin_ids:
        log.warning("ADMIN_IDS is empty: schedule editor will be unavailable")
    if config.group_chat_id is None:
        log.warning("GROUP_CHAT_ID not set: bot will only work in admin DMs")

    await init_db()
    bot = Bot(config.bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(setup_routers())
    await setup_commands(bot)

    poll_task = None
    if config.notifications_enabled and config.group_chat_id is not None:
        poll_task = asyncio.create_task(poller(bot), name="replacements-poller")

    log.info("Starting: timezone=%s, admins=%d, group=%s, notifications=%s",
             config.tz_name, len(config.admin_ids), config.group_chat_id,
             "enabled" if poll_task is not None else "disabled")
    try:
        await dp.start_polling(bot)
    finally:
        if poll_task is not None:
            poll_task.cancel()
            await asyncio.gather(poll_task, return_exceptions=True)
        await bot.session.close()
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
