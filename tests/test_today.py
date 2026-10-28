"""/today: today's schedule only, taking the upper/lower week into account."""
import asyncio
from datetime import datetime

import pytest

from config import config
from database import close_db, init_db, queries
from utils.schedule import schedule_logic as lg
from utils.schedule.schedule_views import today_message


@pytest.fixture
def run():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(init_db())
    yield loop.run_until_complete
    loop.run_until_complete(close_db())
    loop.close()


def lesson(day, number, week, subject):
    return lg.Lesson(number=number, week=week, subject=subject, room="", teacher="", day=day)


def setup(run, parity):
    today = datetime.now(config.tz).date()
    wd = today.weekday()
    other = (wd + 1) % 7
    for day in range(7):
        run(queries.replace_day(day, []))
    run(queries.replace_day(wd, [lesson(wd, 1, lg.BOTH, "Математика"), lesson(wd, 2, lg.UPPER, "Верхняя-пара"),
                                 lesson(wd, 3, lg.LOWER, "Нижняя-пара")]))
    run(queries.replace_day(other, [lesson(other, 1, lg.BOTH, "ЧужойДень")]))
    run(queries.set_setting("anchor_monday", lg.monday_of(today).isoformat()))
    run(queries.set_setting("anchor_parity", parity))


def test_only_today_and_current_parity(run):
    setup(run, lg.UPPER)
    html = run(today_message()).html
    assert "Математика" in html and "Верхняя-пара" in html
    assert "Нижняя-пара" not in html and "ЧужойДень" not in html


def test_lower_week(run):
    setup(run, lg.LOWER)
    html = run(today_message()).html
    assert "Нижняя-пара" in html and "Верхняя-пара" not in html


def test_unknown_parity_gives_text_answer(run):
    for key in ("anchor_monday", "anchor_parity"):
        run(queries.set_setting(key, ""))
    assert isinstance(run(today_message()), str)


def test_free_day_says_no_lessons(run):
    setup(run, lg.UPPER)
    wd = datetime.now(config.tz).date().weekday()
    run(queries.replace_day(wd, []))
    assert "занятий нет" in run(today_message()).html
