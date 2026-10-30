"""ИИ-собеседник в рабочей группе: отвечает выборочно, помнит короткий диалог (в БД), ругается и троллит."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import Message

from config import config
from database.ai_queries import add_message, get_context
from utils.ai import client
from utils.ai.mentions import participants, render_mentions
from utils.ai.persona import build_messages, clean_reply, name_pattern
from utils.ai.policy import Decision, Gate
from utils.common.filters import InGroup

log = logging.getLogger(__name__)
router = Router(name="ai")
router.message.filter(InGroup())

NAME = config.ai_names[0]
_name_re = name_pattern(config.ai_names)
_gate = Gate(
    random_chance=config.ai_random_chance,
    absence_chance=config.ai_absence_chance,
    followup_chance=config.ai_followup_chance,
    cooldown=config.ai_cooldown,
    max_per_hour=config.ai_max_per_hour,
)
_locks: dict[int, asyncio.Lock] = {}
_tasks: set[asyncio.Task] = set()


def _author(message: Message) -> str:
    """Короткое имя без лишних символов: оно же используется для упоминаний."""
    user = message.from_user
    name = (user.first_name or user.full_name) if user else "?"
    return " ".join(name.split())[:32] or "?"


def _is_direct(message: Message, text: str, bot_id: int, username: str | None) -> bool:
    """Обратились к боту: по имени, по @username или ответом на его сообщение."""
    if _name_re.search(text):
        return True
    if username and f"@{username.lower()}" in text.lower():
        return True
    reply = message.reply_to_message
    return bool(reply and reply.from_user and reply.from_user.id == bot_id)


async def _respond(message: Message, bot_id: int, decision: Decision) -> None:
    chat_id = message.chat.id
    async with _locks.setdefault(chat_id, asyncio.Lock()):
        history = await get_context(chat_id, config.ai_history_limit)
        if decision.forced:
            try:
                await message.bot.send_chat_action(chat_id, "typing")
            except TelegramAPIError:
                pass
        people = {n: uid for n, uid in participants(history).items() if uid != bot_id} if config.ai_mentions else {}
        raw = await client.complete(build_messages(
            NAME, history, forced=decision.forced, creator_ids=config.admin_ids, people=people))
        reply = clean_reply(raw, NAME)
        if reply is None:
            log.debug("AI промолчал (reason=%s)", decision.reason)
            return
        try:
            try:
                await message.reply(render_mentions(reply, people), parse_mode="HTML")
            except TelegramBadRequest:  # кривая разметка - шлём как есть
                await message.reply(reply, parse_mode=None)
        except TelegramAPIError as exc:
            log.warning("AI: не удалось отправить ответ: %s", exc)
            return
        await add_message(chat_id, bot_id, "assistant", NAME, reply,
                          keep=config.ai_history_limit, ttl_hours=config.ai_history_ttl_hours)


@router.message(F.text)
async def ai_listener(message: Message, bot: Bot) -> None:
    """Всегда в конце бросает SkipHandler, чтобы реакции (reactions.py) продолжали работать."""
    user = message.from_user
    text = (message.text or "").strip()
    if not config.ai_enabled or user is None or user.is_bot or not text or text.startswith("/"):
        raise SkipHandler
    me = await bot.me()
    chat_id = message.chat.id
    direct = _is_direct(message, text, me.id, me.username)

    await add_message(chat_id, user.id, "user", _author(message), text,
                      keep=config.ai_history_limit, ttl_hours=config.ai_history_ttl_hours)
    decision = _gate.decide(chat_id, user.id, text, direct=direct)
    if decision.reply:
        _gate.mark_replied(chat_id, user.id)
        task = asyncio.create_task(_respond(message, me.id, decision), name="ai-reply")
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    raise SkipHandler
