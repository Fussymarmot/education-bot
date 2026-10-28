"""Pure helpers for the schedule plugin (no aiogram / SQLAlchemy imports, easy to unit-test)."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from html import escape

UPPER, LOWER, BOTH = "upper", "lower", "both"
WEEK_LABEL = {UPPER: "верхняя", LOWER: "нижняя"}
SHIFTS = (1, 2)
DEFAULT_DAY = -1      # bells stored with this day apply to every day without its own override

DAY_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]  # index == date.weekday()
DAY_FULL = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
MONTHS_GEN = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]

MAX_NUMBER = 12      # highest lesson number
MAX_SUBJECT = 120
MAX_ROOM = 20
MAX_TEACHER = 60
MAX_NOTE = 60

_EMPTY_ITEMS = {"-", "—", "–", "нет", "окно"}


@dataclass(frozen=True)
class Bell:
    number: int
    start: str          # "HH:MM"
    end: str            # "HH:MM"
    note: str = ""
    shift: int = 0


@dataclass(frozen=True)
class Lesson:
    number: int
    week: str           # UPPER | LOWER | BOTH
    subject: str
    room: str = ""
    teacher: str = ""
    day: int = -1       # 0=Mon; -1 until the caller assigns it


@dataclass(frozen=True)
class LessonRow:
    number: int
    time: str
    subject: str
    room: str
    teacher: str


@dataclass(frozen=True)
class DayView:
    day: int
    title: str
    rows: list[LessonRow]


# --------------------------------------------------------------------------- bells
_BELL_RE = re.compile(
    r"^\s*(\d{1,2})\s*[.)]?\s+(\d{1,2})[:.](\d{2})\s*[-–—]\s*(\d{1,2})[:.](\d{2})\s*(.*?)\s*$"
)


def _hhmm(hour: str, minute: str) -> str | None:
    h, m = int(hour), int(minute)
    return f"{h:02d}:{m:02d}" if h <= 23 and m <= 59 else None


def parse_bells(text: str) -> tuple[list[Bell], list[str]]:
    """Lines like `1 08:30-10:00 optional note` -> (bells, errors)."""
    bells: list[Bell] = []
    errors: list[str] = []
    seen: set[int] = set()
    for index, raw in enumerate((text or "").splitlines(), 1):
        if not raw.strip():
            continue
        match = _BELL_RE.match(raw)
        if not match:
            errors.append(f"Строка {index}: ожидается «номер ЧЧ:ММ-ЧЧ:ММ», например «1 08:30-10:00».")
            continue
        number = int(match.group(1))
        start = _hhmm(match.group(2), match.group(3))
        end = _hhmm(match.group(4), match.group(5))
        note = match.group(6)
        if not 1 <= number <= MAX_NUMBER:
            errors.append(f"Строка {index}: номер пары должен быть от 1 до {MAX_NUMBER}.")
        elif start is None or end is None:
            errors.append(f"Строка {index}: нет такого времени (часы 0–23, минуты 0–59).")
        elif end <= start:
            errors.append(f"Строка {index}: конец должен быть позже начала.")
        elif len(note) > MAX_NOTE:
            errors.append(f"Строка {index}: заметка длиннее {MAX_NOTE} символов.")
        elif number in seen:
            errors.append(f"Строка {index}: пара №{number} уже указана выше.")
        else:
            seen.add(number)
            bells.append(Bell(number=number, start=start, end=end, note=note))
    if not bells and not errors:
        errors.append("Не нашёл ни одной строки. Пример: «1 08:30-10:00».")
    return sorted(bells, key=lambda b: b.number), errors


def format_bells(bells: list[Bell]) -> str:
    """Inverse of parse_bells (shown to the admin so a list can be copied and edited)."""
    lines = []
    for b in sorted(bells, key=lambda x: x.number):
        lines.append(f"{b.number} {b.start}-{b.end}" + (f" {b.note}" if b.note else ""))
    return "\n".join(lines)


def build_bell_rows(by_shift: dict[int, dict[int, Bell]]) -> list[list[str]]:
    """Rows [number, shift 1, shift 2] for every lesson number present in any shift."""
    numbers = sorted({n for bells in by_shift.values() for n in bells})

    def cell(shift: int, number: int) -> str:
        bell = by_shift.get(shift, {}).get(number)
        if bell is None:
            return "—"
        return f"{bell.start}–{bell.end}" + (f" ({bell.note})" if bell.note else "")

    return [[str(n), cell(1, n), cell(2, n)] for n in numbers]


def effective_bells(by_day: dict[int, dict[int, dict[int, Bell]]], day: int, shift: int) -> dict[int, Bell]:
    """Bells of `shift` on weekday `day`: the day's own list if set, else the common one (Mon–Sat only)."""
    own = by_day.get(day, {}).get(shift)
    if own:
        return own
    if day == 6:
        return {}
    return by_day.get(DEFAULT_DAY, {}).get(shift, {})


def format_days(days: list[int]) -> str:
    """[0,1,2,4] -> "Mon–Wed, Fri"; runs of 3+ become ranges."""
    days = sorted(set(days))
    parts: list[str] = []
    i = 0
    while i < len(days):
        j = i
        while j + 1 < len(days) and days[j + 1] == days[j] + 1:
            j += 1
        if j - i >= 2:
            parts.append(f"{DAY_SHORT[days[i]]}–{DAY_SHORT[days[j]]}")
        else:
            parts.extend(DAY_SHORT[d] for d in days[i:j + 1])
        i = j + 1
    return ", ".join(parts)


def build_bell_groups(by_day: dict[int, dict[int, dict[int, Bell]]]) -> list[tuple[str, list[list[str]]]]:
    """Group weekdays with identical bell schedules -> [("Mon–Fri", rows), ...].

    The title is empty when one table covers Mon–Sat (no per-day differences).
    """
    groups: dict[tuple, tuple[list[int], list[list[str]]]] = {}
    for day in range(7):
        rows = build_bell_rows({s: effective_bells(by_day, day, s) for s in SHIFTS})
        if not rows:
            continue
        key = tuple(tuple(r) for r in rows)
        groups.setdefault(key, ([], rows))[0].append(day)
    result = [(format_days(days), rows) for days, rows in groups.values()]
    if len(groups) == 1 and next(iter(groups.values()))[0] == list(range(6)):
        return [("", result[0][1])]
    return result


# --------------------------------------------------------------------------- lessons
_LINE_RE = re.compile(r"^\s*(\d{1,2})\s*[.)]?\s+(.+?)\s*$")
# "upper:" and "lower:" prefixes at the start of a line or after a space.
_MARK_RE = re.compile(r"(?:(?<=\s)|^)(верх\w*|ниж\w*|в|н)\s*:", re.IGNORECASE)


def _parse_item(raw: str) -> tuple[str, str, str]:
    """`Subject[, room[, teacher]]` -> (subject, room, teacher)."""
    parts = [p.strip() for p in raw.split(",", 2)]
    subject = parts[0]
    room = parts[1] if len(parts) > 1 else ""
    teacher = parts[2] if len(parts) > 2 else ""
    if not subject:
        raise ValueError("не указан предмет")
    if len(subject) > MAX_SUBJECT:
        raise ValueError(f"предмет длиннее {MAX_SUBJECT} символов")
    if len(room) > MAX_ROOM:
        raise ValueError(f"аудитория длиннее {MAX_ROOM} символов")
    if len(teacher) > MAX_TEACHER:
        raise ValueError(f"имя преподавателя длиннее {MAX_TEACHER} символов")
    return subject, room, teacher


def parse_day(text: str) -> tuple[list[Lesson], list[str]]:
    """Parse the schedule of one day.

    `1 Математика, 301`                         — both weeks
    `2 в: Физика, 205 / н: Информатика, 112`    — different on upper / lower week
    `3 н: Английский`                           — lower week only (upper week: no lesson)
    `4 в: Химия / н: -`                         — «-», «—», «нет», «окно» = no lesson that week
    """
    lessons: list[Lesson] = []
    errors: list[str] = []
    taken: dict[int, set[str]] = defaultdict(set)

    for index, raw in enumerate((text or "").splitlines(), 1):
        if not raw.strip():
            continue
        line = _LINE_RE.match(raw)
        if not line:
            errors.append(f"Строка {index}: ожидается «номер предмет», например «1 Математика, 301».")
            continue
        number, rest = int(line.group(1)), line.group(2)
        if not 1 <= number <= MAX_NUMBER:
            errors.append(f"Строка {index}: номер пары должен быть от 1 до {MAX_NUMBER}.")
            continue

        marks = list(_MARK_RE.finditer(rest))
        variants: list[tuple[str, str]] = []
        if not marks:
            variants.append((BOTH, rest))
        else:
            if rest[: marks[0].start()].strip():
                errors.append(f"Строка {index}: перед меткой «в:» / «н:» не должно быть текста.")
                continue
            for i, mark in enumerate(marks):
                end = marks[i + 1].start() if i + 1 < len(marks) else len(rest)
                week = UPPER if mark.group(1)[0].lower() == "в" else LOWER
                variants.append((week, rest[mark.end():end]))

        weeks = [w for w, _ in variants]
        if len(set(weeks)) != len(weeks):
            errors.append(f"Строка {index}: метка «в:» или «н:» повторяется.")
            continue

        parsed: list[Lesson] = []
        failed = False
        for week, item in variants:
            item = item.strip().rstrip("/|;").strip()
            if not item:
                errors.append(f"Строка {index}: после метки пусто (для «нет пары» поставьте «-»).")
                failed = True
                break
            if item.casefold() in _EMPTY_ITEMS:
                continue
            try:
                subject, room, teacher = _parse_item(item)
            except ValueError as exc:
                errors.append(f"Строка {index}: {exc}.")
                failed = True
                break
            parsed.append(Lesson(number=number, week=week, subject=subject, room=room, teacher=teacher))
        if failed:
            continue

        clash = any(
            lesson.week in taken[number] or BOTH in taken[number]
            or (lesson.week == BOTH and taken[number])
            for lesson in parsed
        )
        if clash:
            errors.append(f"Строка {index}: пара №{number} уже задана выше для этой недели.")
            continue
        for lesson in parsed:
            taken[number].add(lesson.week)
        lessons.extend(parsed)

    return sorted(lessons, key=lambda x: (x.number, x.week)), errors


def _format_item(lesson: Lesson) -> str:
    text = lesson.subject
    if lesson.room or lesson.teacher:
        text += f", {lesson.room}"
    if lesson.teacher:
        text += f", {lesson.teacher}"
    return text


def format_day(lessons: list[Lesson]) -> str:
    """Inverse of parse_day (shown to the admin so a day can be copied and edited)."""
    by_number: dict[int, dict[str, Lesson]] = defaultdict(dict)
    for lesson in lessons:
        by_number[lesson.number][lesson.week] = lesson
    lines = []
    for number in sorted(by_number):
        variants = by_number[number]
        if BOTH in variants:
            lines.append(f"{number} {_format_item(variants[BOTH])}")
            continue
        parts = []
        if UPPER in variants:
            parts.append(f"в: {_format_item(variants[UPPER])}")
        if LOWER in variants:
            parts.append(f"н: {_format_item(variants[LOWER])}")
        lines.append(f"{number} " + " / ".join(parts))
    return "\n".join(lines)


def build_week(
    lessons: list[Lesson],
    parity: str,
    bells_by_day: dict[int, dict[int, Bell]] | None = None,
    monday: date | None = None,
) -> list[DayView]:
    """Resolve the schedule of one concrete week (upper or lower) into per-day tables.

    Monday–Friday are always listed; Saturday/Sunday only when something is scheduled on them.
    """
    busy_days = {lesson.day for lesson in lessons}
    result: list[DayView] = []
    for day in range(7):
        if day > 4 and day not in busy_days:
            continue
        bells = (bells_by_day or {}).get(day, {})
        rows = [
            LessonRow(
                number=lesson.number,
                time=(f"{bells[lesson.number].start}–{bells[lesson.number].end}"
                      if lesson.number in bells else ""),
                subject=lesson.subject, room=lesson.room, teacher=lesson.teacher,
            )
            for lesson in sorted(lessons, key=lambda x: x.number)
            if lesson.day == day and lesson.week in (BOTH, parity)
        ]
        title = DAY_FULL[day]
        if monday is not None:
            title += f" · {(monday + timedelta(days=day)):%d.%m}"
        result.append(DayView(day=day, title=title, rows=rows))
    return result


# --------------------------------------------------------------------------- upper / lower week
def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def other_parity(parity: str) -> str:
    return LOWER if parity == UPPER else UPPER


def week_parity(day: date, anchor_monday: date | None, anchor_parity: str | None) -> str | None:
    """Parity of the week containing `day`, given one week whose parity is known. None if unknown."""
    if anchor_monday is None or anchor_parity not in (UPPER, LOWER):
        return None
    weeks = (monday_of(day) - monday_of(anchor_monday)).days // 7
    return anchor_parity if weeks % 2 == 0 else other_parity(anchor_parity)


def reference_day(today: date) -> date:
    """The day whose week is shown as «current»: on Sunday that is already the coming week."""
    return today + timedelta(days=1) if today.weekday() == 6 else today


def format_week_range(monday: date) -> str:
    end = monday + timedelta(days=6)
    if monday.month == end.month:
        return f"{monday.day}–{end.day} {MONTHS_GEN[end.month - 1]}"
    return f"{monday.day} {MONTHS_GEN[monday.month - 1]} – {end.day} {MONTHS_GEN[end.month - 1]}"


# --------------------------------------------------------------------------- plain-text table (fallback)
def text_table(header: list[str], rows: list[list[str]]) -> str:
    """Monospace table for <pre>; HTML-escaped."""
    widths = [max(len(str(row[i])) for row in [header, *rows]) for i in range(len(header))]

    def line(cells: list[str]) -> str:
        return "  ".join(str(c).ljust(widths[i]) for i, c in enumerate(cells)).rstrip()

    rule = "  ".join("-" * w for w in widths)
    return escape("\n".join([line(header), rule, *(line(r) for r in rows)]))
