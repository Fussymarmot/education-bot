from datetime import date

from utils.replacements import replacements_logic as lg

HTML = """
<div id="content">
  <p><strong>ИЗМЕНЕНИЕ В РАСПИСАНИИ НА 16 октября 2026 года</strong></p>
  <p>I СМЕНА</p>
  <table>
    <tr><th>Группа</th><th>Урок</th><th>Дисциплина</th><th>Кабинет</th><th>Преподаватель</th></tr>
    <tr><td>ИС-21</td><td>1</td><td>Математика</td><td>301</td><td>Иванова И.И.</td></tr>
    <tr><td>ИС-22</td><td>2</td><td>Физика</td><td>205</td><td>Петров П.П.</td></tr>
  </table>
  <p>II СМЕНА</p>
  <table>
    <tr><td>Группа</td><td>Урок</td><td>Дисциплина</td></tr>
    <tr><td>ПО-11</td><td>5</td><td>История</td><td>110</td><td>Сидоров С.С.</td></tr>
  </table>
  <p>ИЗМЕНЕНИЯ В РАСПИСАНИИ НА 14 октября 2026 года</p>
  <table><tr><td>ИС-21</td><td>1</td><td>Прошлое</td><td>1</td><td>X</td></tr></table>
</div>
"""
TODAY = date(2026, 10, 15)


def rep(day, group, lesson, subject="Математика", room="301", teacher="Иванова", shift="I смена"):
    return lg.Replacement(day, shift, lg.normalize_cells([group, lesson, subject, room, teacher]))


# --------------------------------------------------------------------------- parsing
def test_parse_dates_shifts_and_rows():
    items = lg.parse_html(HTML)
    assert len(items) == 4
    first = items[0]
    assert (first.date, first.shift, first.group, first.lesson) == (date(2026, 10, 16), "I смена", "ИС-21", "1")
    assert items[2].shift == "II смена" and items[2].group == "ПО-11"
    assert items[3].date == date(2026, 10, 14)


def test_repeated_header_row_is_skipped():
    assert all(i.group != "Группа" for i in lg.parse_html(HTML))


def test_upcoming_drops_past_and_sorts():
    result = lg.upcoming(lg.parse_html(HTML), TODAY)
    assert [i.group for i in result] == ["ИС-21", "ИС-22", "ПО-11"]


def test_parse_date_rejects_garbage():
    assert lg.parse_date("31 февраля 2026 года") is None
    assert lg.parse_date("5 foo 2026 года") is None
    assert lg.parse_date("5 мая 2026 года") == date(2026, 5, 5)


def test_normalize_cells_pads_and_merges():
    assert lg.normalize_cells(["a", "b"]) == ("a", "b", "", "", "")
    assert lg.normalize_cells(list("abcdefg"))[4] == "e f g"


# --------------------------------------------------------------------------- group filter
def test_group_filter_ignores_case_spaces_and_dash():
    item = rep(date(2026, 10, 16), "ИС-21", "1")
    assert lg.matches_group(item, "ис 21") and lg.matches_group(item, "ИС21") and lg.matches_group(item, None)
    assert not lg.matches_group(item, "ИС-22")


def test_clean_group_limits_length():
    assert lg.clean_group("  ") is None and lg.clean_group(None) is None
    assert len(lg.clean_group("x" * 100)) == lg.MAX_GROUP_FILTER


# --------------------------------------------------------------------------- snapshot
def test_snapshot_roundtrip_and_corruption():
    items = lg.parse_html(HTML)
    assert lg.load_snapshot(lg.dump_snapshot(items)) == sorted(items, key=lambda i: i.sort_key)
    assert lg.load_snapshot(None) is None
    assert lg.load_snapshot("not json") is None
    assert lg.load_snapshot('[["bad-date","I смена","a"]]') is None


# --------------------------------------------------------------------------- diff
D = date(2026, 10, 16)


def kinds(changes):
    return sorted((c.kind, c.ref.group) for c in changes)


def test_no_changes_when_identical_or_reordered():
    a, b = rep(D, "ИС-21", "1"), rep(D, "ИС-22", "2")
    assert lg.diff_items([a, b], [b, a]) == []


def test_added_removed_changed():
    a, b = rep(D, "ИС-21", "1"), rep(D, "ИС-22", "2")
    b2 = rep(D, "ИС-22", "2", room="999")
    c = rep(D, "ПО-11", "3")
    changes = lg.diff_items([a, b], [b2, c])
    assert kinds(changes) == [("added", "ПО-11"), ("changed", "ИС-22"), ("removed", "ИС-21")]
    changed = next(x for x in changes if x.kind == "changed")
    assert changed.old.room == "301" and changed.new.room == "999"


def test_cosmetic_differences_are_not_changes():
    a = rep(D, "ИС-21", "1", teacher="Иванова И.И.")
    b = rep(D, "ИС-21", "1", teacher="  иванова  и.и. ")
    assert lg.diff_items([a], [b]) == []


def test_shift_heading_flip_is_silent():
    a = rep(D, "ИС-21", "1", shift=lg.SHIFT_UNKNOWN)
    b = rep(D, "ИС-21", "1", shift="I смена")
    assert lg.diff_items([a], [b]) == []


def test_two_rows_in_one_slot_are_compared_as_multiset():
    a1, a2 = rep(D, "ИС-21", "1", teacher="А"), rep(D, "ИС-21", "1", teacher="Б")
    assert lg.diff_items([a1, a2], [a2, a1]) == []
    changes = lg.diff_items([a1, a2], [a1, rep(D, "ИС-21", "1", teacher="В")])
    assert [c.kind for c in changes] == ["changed"] and changes[0].new.teacher == "В"
    assert [c.kind for c in lg.diff_items([a1], [a1, a2])] == ["added"]


# --------------------------------------------------------------------------- plan_update
def test_first_run_initialises_silently():
    d = lg.plan_update(None, [rep(D, "ИС-21", "1")], TODAY)
    assert d.action == "init" and d.changes == [] and len(d.snapshot) == 1


def test_apply_reports_changes_and_drops_past_items():
    stored = [rep(date(2026, 10, 14), "ИС-21", "1"), rep(D, "ИС-21", "1")]
    d = lg.plan_update(stored, [rep(D, "ИС-21", "1"), rep(D, "ИС-22", "2")], TODAY)
    assert d.action == "apply" and kinds(d.changes) == [("added", "ИС-22")]


def test_page_that_goes_empty_is_held_until_confirmed():
    stored = [rep(D, "ИС-21", "1")]
    d1 = lg.plan_update(stored, [], TODAY, 0)
    assert (d1.action, d1.snapshot, d1.changes, d1.empty_streak) == ("hold", None, [], 1)
    d2 = lg.plan_update(stored, [], TODAY, 1)
    assert d2.action == "hold" and d2.empty_streak == 2
    d3 = lg.plan_update(stored, [], TODAY, 2)
    assert d3.action == "apply" and [c.kind for c in d3.changes] == ["removed"] and d3.empty_streak == 0


def test_empty_to_empty_is_not_held():
    d = lg.plan_update([], [], TODAY, 0)
    assert d.action == "apply" and d.changes == []
