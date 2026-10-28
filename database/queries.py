"""Database queries for schedules and replacements."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, select

from database.engine import read_session, session
from database.models import (
    ReplacementState,
    ScheduleBell,
    ScheduleLesson,
    ScheduleSetting,
)
from utils.schedule import schedule_logic as lg


@dataclass(frozen=True)
class Settings:
    anchor_monday: date | None = None
    anchor_parity: str | None = None
    lessons_shift: int = 0          # 0 = do not show lesson times


async def load_settings() -> Settings:
    async with read_session() as s:
        raw = {r.key: r.value for r in (await s.scalars(select(ScheduleSetting))).all()}
    try:
        anchor = date.fromisoformat(raw["anchor_monday"]) if "anchor_monday" in raw else None
    except ValueError:
        anchor = None
    parity = raw.get("anchor_parity")
    shift = int(raw["lessons_shift"]) if raw.get("lessons_shift", "").isdigit() else 0
    return Settings(
        anchor_monday=anchor,
        anchor_parity=parity if parity in (lg.UPPER, lg.LOWER) else None,
        lessons_shift=shift if shift in lg.SHIFTS else 0,
    )


async def set_setting(key: str, value: str) -> None:
    async with session() as s:
        row = await s.get(ScheduleSetting, key)
        if row is None:
            s.add(ScheduleSetting(key=key, value=value))
        else:
            row.value = value


async def load_bells() -> dict[int, dict[int, dict[int, lg.Bell]]]:
    """Bells as {day: {shift: {number: Bell}}}; day -1 = regular days, 0..6 = custom per weekday."""
    result: dict[int, dict[int, dict[int, lg.Bell]]] = {}
    async with read_session() as s:
        rows = (await s.scalars(
            select(ScheduleBell).order_by(ScheduleBell.day, ScheduleBell.shift, ScheduleBell.number)
        )).all()
    for r in rows:
        result.setdefault(r.day, {}).setdefault(r.shift, {})[r.number] = lg.Bell(
            number=r.number, start=r.starts_at, end=r.ends_at, note=r.note or "", shift=r.shift
        )
    return result


async def load_lessons(day: int | None = None) -> list[lg.Lesson]:
    statement = select(ScheduleLesson).order_by(ScheduleLesson.day, ScheduleLesson.number, ScheduleLesson.week)
    if day is not None:
        statement = statement.where(ScheduleLesson.day == day)
    async with read_session() as s:
        rows = (await s.scalars(statement)).all()
    return [
        lg.Lesson(number=r.number, week=r.week, subject=r.subject, room=r.room or "",
                  teacher=r.teacher or "", day=r.day)
        for r in rows
    ]


async def replace_bells(day: int, shift: int, bells: list[lg.Bell]) -> None:
    async with session() as s:
        await s.execute(delete(ScheduleBell).where(ScheduleBell.day == day, ScheduleBell.shift == shift))
        s.add_all(
            ScheduleBell(day=day, shift=shift, number=b.number, starts_at=b.start, ends_at=b.end,
                         note=b.note or None)
            for b in bells
        )


async def replace_day(day: int, lessons: list[lg.Lesson]) -> None:
    async with session() as s:
        await s.execute(delete(ScheduleLesson).where(ScheduleLesson.day == day))
        s.add_all(
            ScheduleLesson(day=day, number=x.number, week=x.week, subject=x.subject,
                           room=x.room or None, teacher=x.teacher or None)
            for x in lessons
        )


async def get_state(key: str) -> str | None:
    async with read_session() as s:
        return await s.scalar(select(ReplacementState.value).where(ReplacementState.key == key))


async def set_state(key: str, value: str) -> None:
    async with session() as s:
        row = await s.get(ReplacementState, key)
        if row is None:
            s.add(ReplacementState(key=key, value=value))
        else:
            row.value = value


SETTING_REPLACEMENTS_GROUP = "replacements_group"


async def get_replacements_group() -> str | None:
    async with read_session() as s:
        value = await s.scalar(select(ScheduleSetting.value).where(ScheduleSetting.key == SETTING_REPLACEMENTS_GROUP))
    return value or None


async def set_replacements_group(group: str | None) -> None:
    if group:
        await set_setting(SETTING_REPLACEMENTS_GROUP, group)
        return
    async with session() as s:
        await s.execute(delete(ScheduleSetting).where(ScheduleSetting.key == SETTING_REPLACEMENTS_GROUP))
