"""Admin panel: schedule editor UI content and keyboard builders."""
from __future__ import annotations

from datetime import datetime
from html import escape

from aiogram.types import InlineKeyboardMarkup

from config import config
from database import queries
from keyboards import admin as kb
from utils.replacements.replacements_logic import clean_group, MAX_GROUP_FILTER
from utils.schedule.schedule_logic import (
    DAY_FULL, DEFAULT_DAY, SHIFTS, format_bells, format_day,
    week_parity, WEEK_LABEL, format_week_range, monday_of
)

Panel = tuple[str, InlineKeyboardMarkup]


def with_notice(text: str, notice: str) -> str:
    """Prepend error/info notice to text."""
    return f"{notice}\n\n{text}" if notice else text


def errors_text(errors: list[str]) -> str:
    """Format error list, show first 6 with ellipsis if more."""
    shown = "\n".join(escape(e) for e in errors[:6])
    return shown + (f"\n...и ещё {len(errors) - 6}" if len(errors) > 6 else "")


def valid_slot(day: int, shift: int) -> bool:
    """Check if day/shift combination is valid."""
    return -1 <= day <= 6 and shift in SHIFTS


def scope_name(day: int) -> str:
    """Display name of a bells scope: the common schedule or a weekday."""
    return "обычные дни" if day == DEFAULT_DAY else DAY_FULL[day]


async def current_bells_text(day: int, shift: int) -> str:
    """Load and format bells schedule for given day/shift."""
    return format_bells(list((await queries.load_bells()).get(day, {}).get(shift, {}).values()))


async def menu_view(notice: str = "") -> Panel:
    """Main admin panel showing schedule status."""
    bells = await queries.load_bells()
    common = bells.get(DEFAULT_DAY, {})
    overrides = len([d for d in range(7) if any(bells.get(d, {}).values())])
    lessons = await queries.load_lessons()
    settings = await queries.load_settings()
    today = datetime.now(config.tz).date()
    parity = week_parity(today, settings.anchor_monday, settings.anchor_parity)
    week = f"сейчас {WEEK_LABEL[parity]}" if parity else "не указана"
    shift = f"{settings.lessons_shift} смена" if settings.lessons_shift else "не показывается"
    repl_group = await queries.get_replacements_group()
    text = (
        f"<tg-emoji emoji-id='{config.icons['panel']}'>🧰</tg-emoji> <b>Редактор расписания</b>\n\n"
        f"<tg-emoji emoji-id='{config.icons['bells']}'>🔔</tg-emoji> Звонки (обычные дни): смена 1 — {len(common.get(1, {}))} зв., смена 2 — {len(common.get(2, {}))} зв."
        + (f", свои расписания: {overrides}" if overrides else "") + "\n"
        f"<tg-emoji emoji-id='{config.icons['lessons']}'>📚</tg-emoji> Занятия: {len({(x.day, x.number) for x in lessons})} пар в неделю\n"
        f"<tg-emoji emoji-id='{config.icons['calendar']}'>📆</tg-emoji> Неделя: {week}\n"
        f"<tg-emoji emoji-id='{config.icons['time']}'>⏳</tg-emoji> Время пар: {shift}\n"
        f"<tg-emoji emoji-id='{config.icons['replacements']}'>🔄</tg-emoji> Замены в группе: {escape(repl_group) if repl_group else 'выключены'}"
    )
    return with_notice(text, notice), kb.menu_kb()


async def bells_menu_view(notice: str = "") -> Panel:
    """Bells schedule menu."""
    bells = await queries.load_bells()
    text = (
        f"<tg-emoji emoji-id='{config.icons['bells']}'>🔔</tg-emoji> <b>Расписание звонков</b>\n\n"
        "«Обычные дни» действуют везде, если у дня нет своего расписания. "
        "Свои звонки можно задать, например, для субботы. ✱ — у дня есть своё расписание."
    )
    own = {d for d in range(7) if any(bells.get(d, {}).values())}
    return with_notice(text, notice), kb.bells_menu_kb(own)


async def bscope_view(day: int, notice: str = "") -> Panel:
    """Bells scope (day) selection and shift choice."""
    bells = (await queries.load_bells()).get(day, {})
    text = f"<tg-emoji emoji-id='{config.icons['bells']}'>🔔</tg-emoji> <b>Звонки · {scope_name(day)}</b>\n\nВыберите смену."
    if day != DEFAULT_DAY:
        text += " Если для смены ничего не задано, берутся звонки обычных дней."
    return with_notice(text, notice), kb.bscope_kb(day, len(bells.get(1, {})), len(bells.get(2, {})))


async def bells_shift_view(day: int, shift: int, notice: str = "") -> Panel:
    """Show bells for specific day/shift."""
    bells = list((await queries.load_bells()).get(day, {}).get(shift, {}).values())
    if bells:
        body = f"<pre>{escape(format_bells(bells))}</pre>"
    elif day == DEFAULT_DAY:
        body = "Пусто."
    else:
        body = "Своего расписания нет — используются звонки обычных дней."
    text = f"<tg-emoji emoji-id='{config.icons['bells']}'>🔔</tg-emoji> <b>Звонки · {scope_name(day)} · смена {shift}</b>\n\n{body}"
    return with_notice(text, notice), kb.bshift_kb(day, shift, bool(bells))


def bells_prompt(day: int, shift: int, current: str, notice: str = "") -> Panel:
    """Prompt for entering bells schedule. Old data will be replaced."""
    text = (
        f"<tg-emoji emoji-id='{config.icons['edit']}'>✏️</tg-emoji> <b>Звонки · {scope_name(day)} · смена {shift}</b>\n\n"
        "Отправьте по строке на звонок: <code>номер ЧЧ:ММ-ЧЧ:ММ</code>. "
        "После времени можно добавить заметку.\n\n"
        "<pre>1 08:30-10:00\n2 10:10-11:40 перерыв 20 мин</pre>"
    )
    if current:
        text += f"\n\nСейчас (можно скопировать и поправить):\n<pre>{escape(current)}</pre>"
    if notice:
        text = f"<tg-emoji emoji-id='{config.icons['warning']}'>⚠️</tg-emoji> {notice}\n\n{text}"
    return text, kb.bells_prompt_kb(day, shift)


def bells_clear_confirm_view(day: int, shift: int) -> Panel:
    """Confirm deletion of bells schedule."""
    what = "Очистить" if day == DEFAULT_DAY else "Убрать своё расписание и вернуть обычные звонки для"
    return f"🗑 {what}: {scope_name(day)} · смена {shift}?", kb.bclear_confirm_kb(day, shift)


async def days_view(notice: str = "") -> Panel:
    lessons = await queries.load_lessons()
    counts = {d: len({x.number for x in lessons if x.day == d}) for d in range(7)}
    text = f"<tg-emoji emoji-id='{config.icons['lessons']}'>📚</tg-emoji> <b>Расписание занятий</b>\n\nВыберите день недели. В скобках — сколько пар в этот день."
    return with_notice(text, notice), kb.days_kb(counts)


async def day_view(day: int, notice: str = "") -> Panel:
    lessons = await queries.load_lessons(day)
    body = f"<pre>{escape(format_day(lessons))}</pre>" if lessons else "В этот день пока ничего нет."
    text = f"<tg-emoji emoji-id='{config.icons['lessons']}'>📚</tg-emoji> <b>{DAY_FULL[day]}</b>\n\n{body}"
    return with_notice(text, notice), kb.day_kb(day, bool(lessons))


def day_prompt(day: int, current: str, notice: str = "") -> Panel:
    text = (
        f"<tg-emoji emoji-id='{config.icons['edit']}'>✏️</tg-emoji> <b>{DAY_FULL[day]}</b>\n\n"
        "Отправьте <b>весь день</b> одним сообщением — по строке на пару, формат "
        "<code>номер предмет, аудитория, преподаватель</code> (аудитория и преподаватель необязательны).\n\n"
        "Если пара зависит от недели, используйте <code>в:</code> (верхняя) и <code>н:</code> (нижняя):\n"
        "<pre>1 Математика, 301, Иванова И.И.\n"
        "2 в: Физика, 205 / н: Информатика, 112\n"
        "3 н: Английский\n"
        "4 в: Химия / н: -</pre>"
        "«-» — в эту неделю пары нет. Старое расписание дня будет заменено."
    )
    if current:
        text += f"\n\nСейчас (можно скопировать и поправить):\n<pre>{escape(current)}</pre>"
    if notice:
        text = f"<tg-emoji emoji-id='{config.icons['warning']}'>⚠️</tg-emoji> {notice}\n\n{text}"
    return text, kb.day_prompt_kb(day)


def day_clear_confirm_view(day: int) -> Panel:
    return f"🗑 Очистить расписание дня «{DAY_FULL[day]}»?", kb.dclear_confirm_kb(day)


async def settings_view(notice: str = "") -> Panel:
    settings = await queries.load_settings()
    today = datetime.now(config.tz).date()
    parity = week_parity(today, settings.anchor_monday, settings.anchor_parity)
    if parity:
        week = (f"Эта неделя ({format_week_range(monday_of(today))}) — <b>{WEEK_LABEL[parity]}</b>. "
                "Дальше недели чередуются автоматически.")
    else:
        week = "Какая неделя идёт сейчас — <b>не указано</b>. Выберите ниже."
    shift = f"<b>{settings.lessons_shift} смена</b>" if settings.lessons_shift else "<b>не показывается</b>"
    text = (
        f"<tg-emoji emoji-id='{config.icons['settings']}'>⚙️</tg-emoji> <b>Верх/низ и смена</b>\n\n"
        f"<tg-emoji emoji-id='{config.icons['calendar']}'>📆</tg-emoji> {week}\n\n"
        f"<tg-emoji emoji-id='{config.icons['time']}'>⏳</tg-emoji> Время пар в расписании занятий: {shift}. Берётся из расписания звонков выбранной смены."
    )
    return with_notice(text, notice), kb.settings_kb(settings.lessons_shift)


async def repl_view(notice: str = "") -> Panel:
    group = await queries.get_replacements_group()
    if group:
        body = f"Автоматически бот присылает в рабочую группу изменения в заменах только для группы <b>{escape(group)}</b>."
    else:
        body = "Группа <b>не выбрана</b> — автоматически замены в рабочую группу не приходят."
    text = f"<tg-emoji emoji-id='{config.icons['replacements']}'>🔄</tg-emoji> <b>Замены в группе</b>\n\n" + body + "\nПо команде /replacements участники видят замены всех групп."
    if config.group_chat_id is None:
        text += f"\n\n<tg-emoji emoji-id='{config.icons['warning']}'>⚠️</tg-emoji> В .env не задан GROUP_CHAT_ID — присылать замены некуда."
    elif not config.notifications_enabled:
        text += f"\n\n<tg-emoji emoji-id='{config.icons['warning']}'>⚠️</tg-emoji> Автоматическая проверка выключена (SHAPT_POLL_INTERVAL=0): замены приходят только по команде /replacements."
    return with_notice(text, notice), kb.repl_kb(bool(group))


def repl_prompt(group: str | None, notice: str = "") -> Panel:
    text = (
        f"<tg-emoji emoji-id='{config.icons['edit']}'>✏️</tg-emoji> <b>Группа для замен</b>\n\n"
        "Отправьте название группы так, как оно указано на сайте колледжа, например <code>ИС-21</code>. "
        "Регистр, пробелы и дефисы не важны, но ищется вхождение: «ИС-2» подойдёт и к ИС-21, и к ИС-22."
    )
    if group:
        text += f"\n\nСейчас: <code>{escape(group)}</code>"
    if notice:
        text = f"<tg-emoji emoji-id='{config.icons['warning']}'>⚠️</tg-emoji> {notice}\n\n{text}"
    return text, kb.repl_prompt_kb()


def parse_group(raw: str) -> tuple[str | None, str]:
    """Admin text -> (group, error). An over-long name is not silently truncated."""
    group = clean_group(raw)
    if group is None:
        return None, "Название группы пустое."
    if len(" ".join(raw.split())) > MAX_GROUP_FILTER:
        return None, f"Слишком длинное название (до {MAX_GROUP_FILTER} символов)."
    return group, ""
