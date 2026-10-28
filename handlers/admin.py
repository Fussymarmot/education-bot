"""Administrator DMs: schedule editor and replacements group selection."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from config import config
from database import queries
from keyboards.callbacks import EdCb
from states.admin import Editor
from utils import panels
from utils.schedule.schedule_logic import (
    parse_bells, parse_day, format_day, UPPER, LOWER, SHIFTS, monday_of
)
from utils.common.filters import IsAdmin, IsPrivate
from utils.common.messaging import edit_panel, try_delete

router = Router(name="admin")
router.message.filter(IsPrivate(), IsAdmin())
router.callback_query.filter(IsPrivate(), IsAdmin())


async def show(callback: CallbackQuery, view: tuple[str, InlineKeyboardMarkup]) -> None:
    if not isinstance(callback.message, Message):
        return
    try:
        await callback.message.edit_text(view[0], reply_markup=view[1], parse_mode="HTML")
    except TelegramBadRequest as exc:
        if "not modified" not in str(exc):
            raise


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    text, markup = await panels.menu_view()
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(EdCb.filter(F.action == "menu"))
async def editor_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await show(callback, await panels.menu_view())


@router.callback_query(EdCb.filter(F.action == "bells"))
async def bells_menu_panel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await show(callback, await panels.bells_menu_view())


@router.callback_query(EdCb.filter(F.action == "bscope"))
async def bells_scope_panel(callback: CallbackQuery, callback_data: EdCb, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    day = callback_data.day
    if -1 <= day <= 6:
        await show(callback, await panels.bscope_view(day))


@router.callback_query(EdCb.filter(F.action == "bshift"))
async def bells_shift_panel(callback: CallbackQuery, callback_data: EdCb, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    day, shift = callback_data.day, callback_data.shift
    if panels.valid_slot(day, shift):
        await show(callback, await panels.bells_shift_view(day, shift))


@router.callback_query(EdCb.filter(F.action == "days"))
async def days_panel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await show(callback, await panels.days_view())


@router.callback_query(EdCb.filter(F.action == "day"))
async def day_panel(callback: CallbackQuery, callback_data: EdCb, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if 0 <= callback_data.day <= 6:
        await show(callback, await panels.day_view(callback_data.day))


@router.callback_query(EdCb.filter(F.action == "settings"))
async def settings_panel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await show(callback, await panels.settings_view())


@router.callback_query(EdCb.filter(F.action == "bedit"))
async def bells_edit(callback: CallbackQuery, callback_data: EdCb, state: FSMContext) -> None:
    day, shift = callback_data.day, callback_data.shift
    if not panels.valid_slot(day, shift) or not isinstance(callback.message, Message):
        await callback.answer()
        return
    await state.clear()
    await state.set_state(Editor.bells)
    await state.update_data(bday=day, shift=shift, panel_chat=callback.message.chat.id,
                            panel_msg=callback.message.message_id)
    await callback.answer()
    await show(callback, panels.bells_prompt(day, shift, await panels.current_bells_text(day, shift)))


@router.message(Editor.bells, F.text, ~F.text.startswith("/"))
async def bells_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    day, shift = data["bday"], data["shift"]
    chat_id, panel = data["panel_chat"], data.get("panel_msg")
    text = message.text
    await try_delete(message)
    bells, errors = parse_bells(text)
    if errors:
        prompt, markup = panels.bells_prompt(day, shift, await panels.current_bells_text(day, shift),
                                             notice=panels.errors_text(errors))
        panel_id = await edit_panel(message.bot, chat_id, panel, prompt, markup)
        await state.update_data(panel_msg=panel_id)
        return
    await queries.replace_bells(day, shift, bells)
    await state.clear()
    view_text, markup = await panels.bells_shift_view(day, shift, f"✅ Сохранено: {len(bells)} пар.")
    await edit_panel(message.bot, chat_id, panel, view_text, markup)


@router.callback_query(EdCb.filter(F.action == "bclear"))
async def bells_clear_ask(callback: CallbackQuery, callback_data: EdCb) -> None:
    day, shift = callback_data.day, callback_data.shift
    await callback.answer()
    if panels.valid_slot(day, shift):
        await show(callback, panels.bells_clear_confirm_view(day, shift))


@router.callback_query(EdCb.filter(F.action == "bclearok"))
async def bells_clear_confirm(callback: CallbackQuery, callback_data: EdCb) -> None:
    day, shift = callback_data.day, callback_data.shift
    if not panels.valid_slot(day, shift):
        await callback.answer()
        return
    await queries.replace_bells(day, shift, [])
    await callback.answer("Готово")
    await show(callback, await panels.bells_shift_view(day, shift))


@router.callback_query(EdCb.filter(F.action == "dedit"))
async def day_edit(callback: CallbackQuery, callback_data: EdCb, state: FSMContext) -> None:
    day = callback_data.day
    if not 0 <= day <= 6 or not isinstance(callback.message, Message):
        await callback.answer()
        return
    await state.clear()
    await state.set_state(Editor.day)
    await state.update_data(day=day, panel_chat=callback.message.chat.id,
                            panel_msg=callback.message.message_id)
    current = format_day(await queries.load_lessons(day))
    await callback.answer()
    await show(callback, panels.day_prompt(day, current))


@router.message(Editor.day, F.text, ~F.text.startswith("/"))
async def day_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    day, chat_id, panel = data["day"], data["panel_chat"], data.get("panel_msg")
    text = message.text
    await try_delete(message)
    lessons, errors = parse_day(text)
    if not errors and not lessons:
        errors = ["Не нашёл ни одной пары. Чтобы очистить день, нажмите «Отмена» и «🗑 Очистить день»."]
    if errors:
        current = format_day(await queries.load_lessons(day))
        prompt, markup = panels.day_prompt(day, current, notice=panels.errors_text(errors))
        panel_id = await edit_panel(message.bot, chat_id, panel, prompt, markup)
        await state.update_data(panel_msg=panel_id)
        return
    await queries.replace_day(day, [replace(x, day=day) for x in lessons])
    await state.clear()
    view_text, markup = await panels.day_view(day, f"✅ Сохранено: {len({x.number for x in lessons})} пар.")
    await edit_panel(message.bot, chat_id, panel, view_text, markup)


@router.callback_query(EdCb.filter(F.action == "dclear"))
async def day_clear_ask(callback: CallbackQuery, callback_data: EdCb) -> None:
    day = callback_data.day
    await callback.answer()
    if 0 <= day <= 6:
        await show(callback, panels.day_clear_confirm_view(day))


@router.callback_query(EdCb.filter(F.action == "dclearok"))
async def day_clear_confirm(callback: CallbackQuery, callback_data: EdCb) -> None:
    day = callback_data.day
    if not 0 <= day <= 6:
        await callback.answer()
        return
    await queries.replace_day(day, [])
    await callback.answer("Очищено")
    await show(callback, await panels.day_view(day))


@router.callback_query(EdCb.filter(F.action == "parity"))
async def set_parity(callback: CallbackQuery, callback_data: EdCb) -> None:
    parity = callback_data.week
    if parity not in (UPPER, LOWER):
        await callback.answer()
        return
    today = datetime.now(config.tz).date()
    await queries.set_setting("anchor_monday", monday_of(today).isoformat())
    await queries.set_setting("anchor_parity", parity)
    await callback.answer("Сохранено")
    await show(callback, await panels.settings_view())


@router.callback_query(EdCb.filter(F.action == "lshift"))
async def set_lessons_shift(callback: CallbackQuery, callback_data: EdCb) -> None:
    if callback_data.shift not in (0, *SHIFTS):
        await callback.answer()
        return
    await queries.set_setting("lessons_shift", str(callback_data.shift))
    await callback.answer("Сохранено")
    await show(callback, await panels.settings_view())


@router.callback_query(EdCb.filter(F.action == "repl"))
async def repl_panel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await show(callback, await panels.repl_view())


@router.callback_query(EdCb.filter(F.action == "redit"))
async def repl_edit(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    await state.clear()
    await state.set_state(Editor.repl_group)
    await state.update_data(panel_chat=callback.message.chat.id, panel_msg=callback.message.message_id)
    await callback.answer()
    await show(callback, panels.repl_prompt(await queries.get_replacements_group()))


@router.message(Editor.repl_group, F.text, ~F.text.startswith("/"))
async def repl_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    chat_id, panel = data["panel_chat"], data.get("panel_msg")
    text = message.text
    await try_delete(message)
    group, error = panels.parse_group(text)
    if group is None:
        prompt, markup = panels.repl_prompt(await queries.get_replacements_group(), notice=error)
        panel_id = await edit_panel(message.bot, chat_id, panel, prompt, markup)
        await state.update_data(panel_msg=panel_id)
        return
    await queries.set_replacements_group(group)
    await state.clear()
    view_text, markup = await panels.repl_view(f"✅ Группа для замен: {group}")
    await edit_panel(message.bot, chat_id, panel, view_text, markup)


@router.callback_query(EdCb.filter(F.action == "rclear"))
async def repl_clear(callback: CallbackQuery) -> None:
    await queries.set_replacements_group(None)
    await callback.answer("Готово")
    await show(callback, await panels.repl_view())
