"""Admin keyboards for editing the timetable."""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import config
from keyboards.callbacks import EdCb
from utils.schedule.schedule_logic import DAY_SHORT, DEFAULT_DAY, UPPER, LOWER


def menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Звонки", callback_data=EdCb(action="bells"), icon_custom_emoji_id=config.icons["bells"])
    b.button(text="Занятия", callback_data=EdCb(action="days"), icon_custom_emoji_id=config.icons["lessons"])
    b.button(text="Верх/низ и смена", callback_data=EdCb(action="settings"), icon_custom_emoji_id=config.icons["settings"])
    b.button(text="Замены в группе", callback_data=EdCb(action="repl"), icon_custom_emoji_id=config.icons["replacements"])
    return b.adjust(2, 1, 1).as_markup()


def bells_menu_kb(days_with_own_bells: set[int]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Обычные дни", callback_data=EdCb(action="bscope", day=DEFAULT_DAY))
    for day in range(7):
        mark = " ✱" if day in days_with_own_bells else ""
        b.button(text=f"{DAY_SHORT[day]}{mark}", callback_data=EdCb(action="bscope", day=day))
    b.button(text="◀️ Назад", callback_data=EdCb(action="menu"))
    return b.adjust(1, 4, 3, 1).as_markup()


def bscope_kb(day: int, count1: int, count2: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"1 смена ({count1})", callback_data=EdCb(action="bshift", day=day, shift=1))
    b.button(text=f"2 смена ({count2})", callback_data=EdCb(action="bshift", day=day, shift=2))
    b.button(text="◀️ К дням", callback_data=EdCb(action="bells"))
    return b.adjust(2, 1).as_markup()


def bshift_kb(day: int, shift: int, has_bells: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Заменить список" if has_bells else "Заполнить",
             callback_data=EdCb(action="bedit", day=day, shift=shift), icon_custom_emoji_id=config.icons["edit"])
    if has_bells:
        label = "🗑 Очистить смену" if day == DEFAULT_DAY else "🗑 Убрать (вернуть обычное)"
        b.button(text=label, callback_data=EdCb(action="bclear", day=day, shift=shift))
    b.button(text="◀️ Назад", callback_data=EdCb(action="bscope", day=day))
    return b.adjust(1).as_markup()


def bells_prompt_kb(day: int, shift: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Отмена", callback_data=EdCb(action="bshift", day=day, shift=shift), icon_custom_emoji_id=config.icons["cancel"])
    return b.as_markup()


def bclear_confirm_kb(day: int, shift: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🗑 Да", callback_data=EdCb(action="bclearok", day=day, shift=shift))
    b.button(text="◀️ Нет, назад", callback_data=EdCb(action="bshift", day=day, shift=shift))
    return b.adjust(1).as_markup()


def days_kb(counts: dict[int, int]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for day in range(7):
        b.button(text=f"{DAY_SHORT[day]} ({counts[day]})", callback_data=EdCb(action="day", day=day))
    b.button(text="◀️ Назад", callback_data=EdCb(action="menu"))
    return b.adjust(4, 3, 1).as_markup()


def day_kb(day: int, has_lessons: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Изменить день" if has_lessons else "Заполнить день",
             callback_data=EdCb(action="dedit", day=day), icon_custom_emoji_id=config.icons["edit"])
    if has_lessons:
        b.button(text="🗑 Очистить день", callback_data=EdCb(action="dclear", day=day))
    b.button(text="◀️ К дням", callback_data=EdCb(action="days"))
    return b.adjust(1).as_markup()


def day_prompt_kb(day: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Отмена", callback_data=EdCb(action="day", day=day), icon_custom_emoji_id=config.icons["cancel"])
    return b.as_markup()


def dclear_confirm_kb(day: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🗑 Да, очистить", callback_data=EdCb(action="dclearok", day=day))
    b.button(text="◀️ Нет, назад", callback_data=EdCb(action="day", day=day))
    return b.adjust(1).as_markup()


def settings_kb(lessons_shift: int) -> InlineKeyboardMarkup:
    def mark(value: int) -> str:
        return "✅ " if lessons_shift == value else ""

    b = InlineKeyboardBuilder()
    b.button(text="⬆️ Эта неделя — верхняя", callback_data=EdCb(action="parity", week=UPPER))
    b.button(text="⬇️ Эта неделя — нижняя", callback_data=EdCb(action="parity", week=LOWER))
    b.button(text=f"{mark(1)}1 смена", callback_data=EdCb(action="lshift", shift=1))
    b.button(text=f"{mark(2)}2 смена", callback_data=EdCb(action="lshift", shift=2))
    b.button(text=f"{mark(0)}Скрыть", callback_data=EdCb(action="lshift", shift=0))
    b.button(text="◀️ Назад", callback_data=EdCb(action="menu"))
    return b.adjust(2, 3, 1).as_markup()


def repl_kb(has_group: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Сменить группу" if has_group else "Выбрать группу", callback_data=EdCb(action="redit"), icon_custom_emoji_id=config.icons["edit"])
    if has_group:
        b.button(text="Не присылать замены", callback_data=EdCb(action="rclear"), icon_custom_emoji_id=config.icons["disable"])
    b.button(text="◀️ Назад", callback_data=EdCb(action="menu"))
    return b.adjust(1).as_markup()


def repl_prompt_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Отмена", callback_data=EdCb(action="repl"), icon_custom_emoji_id=config.icons["cancel"])
    return b.as_markup()
