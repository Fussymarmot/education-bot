"""Send and edit messages: rich tables with HTML fallback."""
from __future__ import annotations

import asyncio
import logging

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup, Message

from utils.replacements.replacements_render import View as ReplacementsView
from utils.schedule.schedule_render import View

log = logging.getLogger(__name__)


async def answer_view(message: Message, view: View, markup: InlineKeyboardMarkup | None = None) -> None:
    """Send rich message if supported, fall back to HTML."""
    if view.rich is not None:
        try:
            await message.answer_rich(view.rich, reply_markup=markup)
            return
        except TelegramBadRequest as exc:
            log.warning("Rich message rejected (%s) - falling back to HTML", exc)
    await message.answer(view.html, parse_mode="HTML", reply_markup=markup)


async def edit_view(bot, message: Message, view: View, markup: InlineKeyboardMarkup | None) -> None:
    """Edit message with rich text if supported, fall back to HTML."""
    async def attempt(**content) -> None:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id, message_id=message.message_id, reply_markup=markup, **content
            )
        except TelegramBadRequest as exc:
            if "not modified" not in str(exc):
                raise

    if view.rich is not None:
        try:
            await attempt(rich_message=view.rich)
            return
        except TelegramBadRequest as exc:
            log.warning("Rich edit rejected (%s) - falling back to HTML", exc)
    await attempt(text=view.html, parse_mode="HTML")


async def send_html(bot, chat_id: int, chunks, **extra) -> None:
    """Send message chunks with HTML formatting."""
    for index, chunk in enumerate(chunks):
        kwargs = dict(extra) if index == len(chunks) - 1 else {}
        try:
            await bot.send_message(chat_id, chunk, parse_mode="HTML", disable_web_page_preview=True, **kwargs)
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 1)
            await bot.send_message(chat_id, chunk, parse_mode="HTML", disable_web_page_preview=True, **kwargs)
        except TelegramAPIError:
            pass


async def answer_replacements_view(
    message: Message, view: ReplacementsView, keyboard: InlineKeyboardMarkup | None
) -> None:
    """Send replacements table as rich message, fall back to HTML."""
    if view.rich is not None:
        try:
            try:
                await message.answer_rich(view.rich, reply_markup=keyboard)
                return
            except (TypeError, ValueError):
                await message.answer_rich(view.rich)
                if keyboard is not None:
                    await message.answer("Обновить замены:", reply_markup=keyboard)
                return
        except Exception as exc:
            log.warning("Не удалось отправить rich message, использую HTML: %s", exc)
    await send_html(message.bot, message.chat.id, view.html, reply_markup=keyboard)


async def try_delete(message: Message) -> None:
    try:
        await message.delete()
    except TelegramAPIError:
        pass  # not critical: only keeps the chat tidy


async def edit_panel(bot, chat_id: int, message_id: int | None, text: str, markup: InlineKeyboardMarkup) -> int:
    """Edit the single editor panel message, or send a new one if it is gone. Returns its id."""
    if message_id:
        try:
            await bot.edit_message_text(
                text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML"
            )
            return message_id
        except TelegramBadRequest as exc:
            if "not modified" in str(exc):
                return message_id
    sent = await bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
    return sent.message_id
