from utils.schedule import schedule_logic as logic
from utils import schedule_render as render


def test_bells_view_has_table_and_html_fallback():
    one = {1: logic.Bell(1, "08:30", "10:00")}
    two = {1: logic.Bell(1, "13:00", "14:30")}
    view = render.bells_view({-1: {1: one, 2: two}})
    assert "08:30–10:00" in view.html and "<pre>" in view.html
    if render.RICH_AVAILABLE:
        kinds = [b.type for b in view.rich.blocks]
        assert kinds == ["heading", "table"]
        assert len(view.rich.blocks[1].cells) == 2          # header + one row


def test_empty_bells_message():
    assert "не заполнено" in render.bells_view({}).html


def test_week_view_one_table_per_busy_day():
    lessons = [logic.Lesson(1, logic.BOTH, "Математика", "301", "Иванова", day=0)]
    days = logic.build_week(lessons, logic.UPPER)
    view = render.week_view(days, subtitle="Верхняя неделя", show_time=False)
    assert "Математика — Иванова" in view.html and "занятий нет" in view.html
    if render.RICH_AVAILABLE:
        assert [b.type for b in view.rich.blocks].count("table") == 1


def test_bells_view_one_table_per_day_group():
    common = {1: {1: logic.Bell(1, "08:30", "10:00")}}
    sat = {1: {1: logic.Bell(1, "09:00", "10:30")}}
    view = render.bells_view({-1: common, 5: sat})
    assert "Пн–Пт" in view.html and "<b>Сб</b>" in view.html and view.html.count("<pre>") == 2
    if render.RICH_AVAILABLE:
        assert [b.type for b in view.rich.blocks] == ["heading", "heading", "table", "heading", "table"]
