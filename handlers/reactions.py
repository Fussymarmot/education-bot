"""Реакции на сообщения в рабочей группе: по ключевым словам и случайные."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message, ReactionTypeEmoji

from config import config
from utils.common.filters import InGroup
from utils.common.reactions import pick_reaction

log = logging.getLogger(__name__)
router = Router(name="reactions")
router.message.filter(InGroup())


@router.message(F.text | F.caption)
async def react_to_message(message: Message) -> None:
    """Подключается ПОСЛЕ users-роутера: команды (/week и т.п.) обрабатываются им и сюда не попадают."""
    if not config.reactions_enabled:
        return
    text = message.text or message.caption or ""
    if text.startswith("/") or (message.from_user and message.from_user.is_bot):
        return
    emoji = pick_reaction(text, config.reaction_chance)
    if emoji is None:
        return
    try:
        await message.react([ReactionTypeEmoji(emoji=emoji)])
    except TelegramAPIError as exc:
        # например REACTION_INVALID, если админы группы отключили этот эмодзи
        log.debug("Не удалось поставить реакцию %s: %s", emoji, exc)
