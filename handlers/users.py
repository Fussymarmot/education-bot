"""Work group (GROUP_CHAT_ID) handlers: bells, schedule, replacements. Inactive in other chats."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from keyboards.callbacks import ReplCb, SchCb
from keyboards.users import replacements_kb
from utils.replacements.replacements_service import build as build_replacements
from utils.schedule.schedule_logic import UPPER, LOWER
from utils.common.commands import GROUP_COMMANDS
from utils.common.filters import InGroup
from utils.common.messaging import answer_replacements_view, answer_view, edit_view
from utils.replacements.replacements_source import URL
from utils.schedule.schedule_views import bells_message, today_message, week_message

log = logging.getLogger(__name__)
router = Router(name="users")
router.message.filter(InGroup())
router.callback_query.filter(InGroup())


# help, bells, schedule
@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer("\n".join(f"/{name} — {description}" for name, description in GROUP_COMMANDS))


@router.message(Command("bells"))
async def bells_command(message: Message) -> None:
    await answer_view(message, await bells_message())


@router.message(Command("today"))
async def today_command(message: Message) -> None:
    view = await today_message()
    if isinstance(view, str):
        await message.answer(view)
    else:
        await answer_view(message, view)


@router.message(Command("week"))
async def week_command(message: Message) -> None:
    """Show week schedule."""
    view, markup = await week_message(None)
    await answer_view(message, view, markup)


@router.callback_query(SchCb.filter(F.action == "p"))
async def switch_parity(callback: CallbackQuery, callback_data: SchCb) -> None:
    if callback_data.value not in (UPPER, LOWER) or not isinstance(callback.message, Message):
        await callback.answer()
        return
    view, markup = await week_message(callback_data.value)
    await callback.answer()
    await edit_view(callback.message.bot, callback.message, view, markup)


# /replacements
async def show_replacements(message: Message, *, force: bool = False) -> None:
    loading = await message.answer("⏳ Загружаю актуальные замены с сайта колледжа…")
    try:
        view = await build_replacements(None, force=force)
        await answer_replacements_view(message, view, replacements_kb())
        try:
            await loading.delete()
        except TelegramAPIError as exc:
            log.debug("Не удалось удалить сообщение о загрузке: %s", exc)
    except Exception:
        log.exception("Не удалось получить замены с сайта %s", URL)
        await message.answer(
            "Не удалось загрузить замены с сайта колледжа. Попробуйте позже.\n"
            f'<a href="{URL}">Открыть страницу замен</a>',
            parse_mode="HTML", disable_web_page_preview=True,
        )


@router.message(Command("replacements"))
async def replacements(message: Message) -> None:
    await show_replacements(message)


@router.callback_query(ReplCb.filter(F.action == "refresh"))
async def replacements_refresh(callback: CallbackQuery) -> None:
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return
    await callback.answer("Обновляю…")
    await show_replacements(message, force=True)
    try:
        await message.delete()
    except TelegramAPIError:
        pass
