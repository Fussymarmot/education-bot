from utils.schedule import schedule_logic as logic
from utils.schedule import schedule_render as render


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


def test_week_view_hides_shift_headings_when_day_has_only_one_shift():
    lessons = [
        logic.Lesson(1, logic.BOTH, "Математика", day=0, shift=1),
        logic.Lesson(2, logic.BOTH, "Физика", day=0, shift=1),
    ]
    days = logic.build_week(lessons, logic.UPPER)
    view = render.week_view(days, subtitle="Верхняя неделя")
    assert "1 смена" not in view.html
    assert "2 смена" not in view.html
    assert "Математика" in view.html and "Физика" in view.html
    if render.RICH_AVAILABLE:
        table = next(block for block in view.rich.blocks if block.type == "table")
        # Header + two lesson rows; no extra shift-section row.
        assert len(table.cells) == 3


def test_week_view_shows_both_shift_headings_when_day_has_both_shifts():
    lessons = [
        logic.Lesson(1, logic.BOTH, "Математика", day=0, shift=1),
        logic.Lesson(1, logic.BOTH, "История", day=0, shift=2),
    ]
    days = logic.build_week(lessons, logic.UPPER)
    view = render.week_view(days, subtitle="Верхняя неделя")
    assert "1 смена" in view.html and "2 смена" in view.html
    if render.RICH_AVAILABLE:
        table = next(block for block in view.rich.blocks if block.type == "table")
        # Header + two shift headings + two lesson rows.
        assert len(table.cells) == 5
