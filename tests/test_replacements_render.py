from datetime import date, timezone

from utils.replacements import replacements_logic as lg
from utils import replacements_render as render

D = date(2026, 10, 16)


def rep(group, lesson, subject="Математика", room="301", teacher="Иванова", day=D, shift="I смена"):
    return lg.Replacement(day, shift, lg.normalize_cells([group, lesson, subject, room, teacher]))


def test_view_groups_by_day_and_shift_and_escapes_html():
    view = render.build_view(
        [rep("ИС-21", "1", subject="A <b> & B"), rep("ПО-11", "5", day=date(2026, 10, 17), shift="II смена")],
        date(2026, 10, 15), tz=timezone.utc, fetched_at=0, source_url="https://example.org/?a=1&b=2",
    )
    html = "\n".join(view.html)
    assert "16.10.2026 (пт) · I смена" in html and "17.10.2026 (сб) · II смена" in html
    assert "A &lt;b&gt; &amp; B" in html and "&amp;b=2" in html
    assert "1 пара" in html and "каб. 301" in html


def test_stale_marker_and_group_in_title():
    view = render.build_view([rep("ИС-21", "1")], date(2026, 10, 15), group="ИС-21", stale=True,
                             fetched_at=0, tz=timezone.utc)
    assert "Сайт недоступен" in view.html[0] and "Замены в расписании · ИС-21" in view.html[0]


def test_empty_views():
    assert "не найдено" in render.build_view([], date(2026, 10, 15)).html[0]
    assert "для группы ИС-99" in render.build_view([], date(2026, 10, 15), group="ИС-99").html[0]


def test_long_output_is_split_below_telegram_limit():
    rows = [rep(f"ГР-{n}", str(n % 6 + 1), subject="Очень длинное название дисциплины " * 3) for n in range(150)]
    view = render.build_view(rows, date(2026, 10, 15))
    assert len(view.html) > 1
    assert all(len(chunk) <= 4096 for chunk in view.html)
    # every row survives and the day heading is repeated in continuation messages
    assert sum(chunk.count("└") for chunk in view.html) == 150
    assert all("16.10.2026" in chunk for chunk in view.html)


def test_change_digest():
    a, b, c = rep("ИС-21", "1"), rep("ИС-22", "2"), rep("ПО-11", "3")
    changes = lg.diff_items([a, b], [rep("ИС-22", "2", room="999"), c])
    text = "\n".join(render.format_changes(changes))
    assert "новых 1, изменено 1, отменено 1" in text
    assert "➕" in text and "✏️" in text and "➖" in text
    assert "было: <s>Математика · каб. 301" in text and "стало: Математика · каб. 999" in text


def test_change_digest_is_chunked():
    changes = [lg.Change(lg.ADDED, new=rep(f"ГР-{n}", "1", subject="Длинное название " * 4)) for n in range(200)]
    chunks = render.format_changes(changes)
    assert len(chunks) > 1 and all(len(c) <= 4096 for c in chunks)
