"""Telegram command menus for public and admin scopes."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from config import config

log = logging.getLogger(__name__)

GROUP_COMMANDS = [
    ("bells", "Расписание звонков"),
    ("today", "Расписание на сегодня"),
    ("week", "Расписание на неделю"),
    ("replacements", "Замены в расписании"),
    ("help", "Список команд"),
]
ADMIN_COMMANDS = [("start", "Редактор расписания")]

PUBLIC = GROUP_COMMANDS


def admin_commands() -> list[tuple[str, str]]:
    """Return admin commands for /help."""
    return ADMIN_COMMANDS


def _commands(items: list[tuple[str, str]]) -> list[BotCommand]:
    """Convert command list to BotCommand objects."""
    return [BotCommand(command=c, description=d) for c, d in items]


async def setup_commands(bot: Bot) -> None:
    """Set up bot commands for different scopes."""
    await bot.delete_my_commands(BotCommandScopeDefault())
    targets = [(config.group_chat_id, GROUP_COMMANDS)] if config.group_chat_id is not None else []
    targets += [(admin_id, ADMIN_COMMANDS) for admin_id in config.admin_ids]
    for chat_id, items in targets:
        try:
            await bot.set_my_commands(_commands(items), BotCommandScopeChat(chat_id=chat_id))
        except TelegramAPIError as exc:
            log.warning("Failed to set commands for chat %s: %s", chat_id, exc)
