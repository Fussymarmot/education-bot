"""Aiogram filters for access control."""
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from config import config


def _chat(event: Message | CallbackQuery):
    message = event.message if isinstance(event, CallbackQuery) else event
    return message.chat if message is not None else None


class IsAdmin(BaseFilter):
    """Only administrators from ADMIN_IDS."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return config.is_admin(user.id if user else None)


class IsPrivate(BaseFilter):
    """Private messages to the bot only."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        chat = _chat(event)
        return chat is not None and chat.type == "private"


class InGroup(BaseFilter):
    """The work group from GROUP_CHAT_ID only."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        chat = _chat(event)
        return chat is not None and config.is_group(chat.id)
