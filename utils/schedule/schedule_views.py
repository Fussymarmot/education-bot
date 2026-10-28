"""Public schedule views for bells and weekly lessons."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from aiogram.types import InlineKeyboardMarkup

from config import config
from database import queries
from keyboards.users import week_kb
from utils.schedule.schedule_logic import (
    week_parity, effective_bells, build_week, DayView, monday_of,
    DAY_FULL, WEEK_LABEL, UPPER, format_week_range, reference_day
)
from utils.schedule.schedule_render import View, bells_view, week_view


async def bells_message() -> View:
    return bells_view(await queries.load_bells())


async def _bells_by_day(lessons_shift: int) -> dict[int, dict] | None:
    if not lessons_shift:
        return None
    all_bells = await queries.load_bells()
    return {d: effective_bells(all_bells, d, lessons_shift) for d in range(7)}


async def today_message() -> View | str:
    """Today's schedule. A plain string when there is nothing to show (week parity is unknown)."""
    settings = await queries.load_settings()
    today = datetime.now(config.tz).date()
    parity = week_parity(today, settings.anchor_monday, settings.anchor_parity)
    if parity is None:
        return "Какая неделя идёт сейчас (верхняя или нижняя), пока не указано — это задаёт администратор."
    bells_by_day = await _bells_by_day(settings.lessons_shift)
    days = build_week(await queries.load_lessons(), parity, bells_by_day, monday_of(today))
    day = next((d for d in days if d.day == today.weekday()), None)
    if day is None:   # a weekend without lessons is not included by build_week
        day = DayView(day=today.weekday(), title=f"{DAY_FULL[today.weekday()]} · {today:%d.%m}", rows=[])
    subtitle = f"Сегодня · {WEEK_LABEL[parity]} неделя"
    return week_view([day], subtitle=subtitle, show_time=bool(bells_by_day and any(bells_by_day.values())))


async def week_message(parity: str | None) -> tuple[View, InlineKeyboardMarkup]:
    """Weekly schedule. `parity=None` means the current week; the buttons switch upper/lower."""
    settings = await queries.load_settings()
    today = datetime.now(config.tz).date()
    ref = reference_day(today)                   # on Sunday the "current" week is already the next one
    current = week_parity(ref, settings.anchor_monday, settings.anchor_parity)
    shown = parity or current or UPPER

    monday: date | None = None
    if current is not None:
        monday = monday_of(ref) if shown == current else monday_of(ref) + timedelta(days=7)

    subtitle = f"{WEEK_LABEL[shown].capitalize()} неделя"
    if monday is not None:
        subtitle += f" · {format_week_range(monday)}"
    if current is None:
        note = "Какая неделя идёт сейчас, пока не указано — переключайте верхнюю и нижнюю кнопками."
    elif shown != current:
        note = "Это расписание следующей недели."
    elif today != ref:
        note = "Сегодня воскресенье — показана ближайшая неделя."
    else:
        note = ""

    bells_by_day = await _bells_by_day(settings.lessons_shift)
    days = build_week(await queries.load_lessons(), shown, bells_by_day, monday)
    view = week_view(days, subtitle=subtitle, note=note,
                     show_time=bool(bells_by_day and any(bells_by_day.values())))
    return view, week_kb(shown)
