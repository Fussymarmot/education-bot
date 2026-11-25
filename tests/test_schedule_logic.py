from datetime import date

from utils.schedule import schedule_logic as logic

UPPER, LOWER, BOTH = logic.UPPER, logic.LOWER, logic.BOTH


# --------------------------------------------------------------------------- bells
def test_parse_bells_ok():
    bells, errors = logic.parse_bells("1 08:30-10:00\n2. 10:10 – 11:40 перерыв 5 мин\n\n3) 8.00-9.30")
    assert not errors
    assert [(b.number, b.start, b.end, b.note) for b in bells] == [
        (1, "08:30", "10:00", ""),
        (2, "10:10", "11:40", "перерыв 5 мин"),
        (3, "08:00", "09:30", ""),
    ]


def test_parse_bells_errors():
    _, errors = logic.parse_bells("08:30-10:00\n1 25:00-26:00\n2 10:00-09:00\n3 09:00-10:00\n3 10:00-11:00\n99 09:00-10:00")
    assert len(errors) == 5
    assert logic.parse_bells("")[1]          # nothing to save is reported, not silently accepted


def test_bells_roundtrip():
    text = "1 08:30-10:00\n2 10:10-11:40 заметка"
    bells, errors = logic.parse_bells(text)
    assert not errors and logic.format_bells(bells) == text


def test_bell_rows_two_shifts():
    one = {1: logic.Bell(1, "08:30", "10:00"), 2: logic.Bell(2, "10:10", "11:40", "обед")}
    two = {1: logic.Bell(1, "13:00", "14:30")}
    assert logic.build_bell_rows({1: one, 2: two}) == [
        ["1", "08:30–10:00", "13:00–14:30"],
        ["2", "10:10–11:40 (обед)", "—"],
    ]
    assert logic.build_bell_rows({}) == []


# --------------------------------------------------------------------------- lessons
def test_parse_day_both_and_split_weeks():
    lessons, errors = logic.parse_day(
        "1 Математика, 301, Иванова И.И.\n"
        "2 в: Физика, 205 / н: Информатика, 112\n"
        "3 н: Английский\n"
        "4 верх: Химия / ниж: -\n"
        "5 Физ-ра"
    )
    assert not errors
    got = [(x.number, x.week, x.subject, x.room, x.teacher) for x in lessons]
    assert (1, BOTH, "Математика", "301", "Иванова И.И.") in got
    assert (2, UPPER, "Физика", "205", "") in got
    assert (2, LOWER, "Информатика", "112", "") in got
    assert (3, LOWER, "Английский", "", "") in got
    assert (4, UPPER, "Химия", "", "") in got
    assert not any(x.number == 4 and x.week == LOWER for x in lessons)   # "-" = no lesson
    assert (5, BOTH, "Физ-ра", "", "") in got


def test_parse_day_slash_inside_subject_and_teacher_without_room():
    lessons, errors = logic.parse_day("1 Алгебра/геометрия, , Петров П.П.")
    assert not errors
    assert (lessons[0].subject, lessons[0].room, lessons[0].teacher) == ("Алгебра/геометрия", "", "Петров П.П.")


def test_parse_day_errors():
    _, errors = logic.parse_day("Математика\n0 Физика\n13 Химия\n1 текст в: Физика\n2 в: A / в: B\n3 в:\n4 Что-то\n4 н: Другое")
    assert len(errors) == 7


def test_parse_day_conflicts():
    _, errors = logic.parse_day("1 Математика\n1 в: Физика")
    assert errors                                   # "both" clashes with "upper"
    lessons, errors = logic.parse_day("1 в: Математика\n1 н: Физика")
    assert not errors and len(lessons) == 2         # same number on different weeks is fine
    assert logic.parse_day("")[0] == [] and logic.parse_day("")[1] == []


def test_day_roundtrip():
    text = (
        "1 Математика, 301, Иванова И.И.\n"
        "2 в: Физика, 205 / н: Информатика, 112\n"
        "3 н: Английский\n"
        "4 Лекция, , Сидоров С.С."
    )
    lessons, errors = logic.parse_day(text)
    assert not errors
    assert logic.format_day(lessons) == text


def test_build_week_resolves_parity_and_hides_empty_weekend():
    def L(day, number, week, subject):
        return logic.Lesson(number=number, week=week, subject=subject, day=day)

    lessons = [
        L(0, 1, BOTH, "Математика"),
        L(0, 2, UPPER, "Физика"), L(0, 2, LOWER, "Информатика"),
        L(1, 1, LOWER, "Английский"),
    ]
    bells = {1: {1: logic.Bell(1, "08:30", "10:00"), 2: logic.Bell(2, "10:10", "11:40")}}
    monday = date(2026, 10, 12)

    upper = logic.build_week(lessons, UPPER, {0: bells}, monday, default_shift=1)
    assert [d.day for d in upper] == [0, 1, 2, 3, 4]                       # no Sat/Sun
    assert upper[0].title == "Понедельник · 12.10"
    assert [(r.number, r.subject, r.time) for r in upper[0].rows] == [
        (1, "Математика", "08:30–10:00"), (2, "Физика", "10:10–11:40")]
    assert upper[1].rows == []                                             # Tuesday: only lower-week lesson

    lower = logic.build_week(lessons, LOWER)
    assert [r.subject for r in lower[0].rows] == ["Математика", "Информатика"]
    assert [r.subject for r in lower[1].rows] == ["Английский"]
    assert lower[0].rows[0].time == "" and lower[0].title == "Понедельник"

    with_saturday = logic.build_week([*lessons, L(5, 1, BOTH, "Консультация")], UPPER)
    assert with_saturday[-1].day == 5 and with_saturday[-1].rows


# --------------------------------------------------------------------------- upper / lower
def test_week_parity_alternates_around_anchor():
    anchor = date(2026, 10, 14)               # Wednesday of the week starting Mon 12.10
    p = lambda d: logic.week_parity(d, anchor, UPPER)  # noqa: E731
    assert p(date(2026, 10, 12)) == UPPER and p(date(2026, 10, 18)) == UPPER   # Mon..Sun of the anchor week
    assert p(date(2026, 10, 19)) == LOWER and p(date(2026, 10, 26)) == UPPER
    assert p(date(2026, 10, 5)) == LOWER and p(date(2026, 9, 28)) == UPPER     # earlier weeks (negative offset)
    assert p(date(2027, 1, 4)) == logic.week_parity(date(2027, 1, 4), date(2026, 10, 12), UPPER)
    assert logic.week_parity(anchor, None, None) is None
    assert logic.week_parity(anchor, anchor, "garbage") is None


def test_reference_day_moves_sunday_to_next_week():
    assert logic.reference_day(date(2026, 10, 17)) == date(2026, 10, 17)       # Saturday stays
    assert logic.reference_day(date(2026, 10, 18)) == date(2026, 10, 19)       # Sunday -> Monday


def test_format_week_range():
    assert logic.format_week_range(date(2026, 10, 12)) == "12–18 октября"
    assert logic.format_week_range(date(2026, 10, 26)) == "26 октября – 1 ноября"


def test_text_table_escapes_html():
    table = logic.text_table(["№", "Предмет"], [["1", "A<B"]])
    assert "A&lt;B" in table and table.splitlines()[1].startswith("-")


# --------------------------------------------------------------------------- bells differ by weekday
def _b(n, s, e):
    return logic.Bell(n, s, e)


def test_effective_bells_override_and_sunday():
    by_day = {
        -1: {1: {1: _b(1, "08:30", "10:00")}, 2: {1: _b(1, "13:00", "14:30")}},
        5: {1: {1: _b(1, "09:00", "10:30")}},                     # Saturday: own 1st shift only
    }
    assert logic.effective_bells(by_day, 0, 1)[1].start == "08:30"    # common
    assert logic.effective_bells(by_day, 5, 1)[1].start == "09:00"    # override wins
    assert logic.effective_bells(by_day, 5, 2)[1].start == "13:00"    # 2nd shift not overridden -> common
    assert logic.effective_bells(by_day, 6, 1) == {}                  # Sunday only with its own list


def test_bell_groups_merge_identical_days():
    common = {1: {1: _b(1, "08:30", "10:00")}}
    only_common = logic.build_bell_groups({-1: common})
    assert only_common == [("", [["1", "08:30–10:00", "—"]])]          # one table, no subheading

    by_day = {-1: common, 2: {1: {1: _b(1, "08:00", "09:30")}}, 5: {1: {1: _b(1, "09:00", "10:30")}}}
    groups = logic.build_bell_groups(by_day)
    assert [t for t, _ in groups] == ["Пн, Вт, Чт, Пт", "Ср", "Сб"]
    assert groups[1][1][0][1] == "08:00–09:30" and groups[2][1][0][1] == "09:00–10:30"
    assert logic.build_bell_groups({}) == []


def test_format_days():
    assert logic.format_days([0, 1, 2, 3, 4]) == "Пн–Пт"
    assert logic.format_days([0, 1, 3, 4, 5]) == "Пн, Вт, Чт–Сб"
    assert logic.format_days([5]) == "Сб"


# --------------------------------------------------------------------------- lessons in different shifts
def test_shift_tag_variants():
    assert logic.split_shift_tag("[2см] Физика") == (2, "Физика")
    assert logic.split_shift_tag("[2] Физика") == (2, "Физика")
    assert logic.split_shift_tag("(1 см) Физика") == (1, "Физика")
    assert logic.split_shift_tag("[2 смена] Физика") == (2, "Физика")
    assert logic.split_shift_tag("2см Физика") == (2, "Физика")
    assert logic.split_shift_tag("2 Физика") == (0, "2 Физика")          # no «см» -> not a tag
    assert logic.split_shift_tag("[3см] Физика") == (0, "[3см] Физика")  # only shifts 1 and 2
    assert logic.split_shift_tag("Физика") == (0, "Физика")


def test_parse_day_shift_per_lesson():
    lessons, errors = logic.parse_day(
        "1 Математика, 301\n"
        "2 Физика\n"
        "1 [2см] Информатика, 112\n"
        "2 [2см] в: Химия / н: -\n"
        "3 в: [1см] Био / н: [2см] Гео"
    )
    assert not errors
    got = {(x.shift, x.number, x.week, x.subject) for x in lessons}
    assert (0, 1, BOTH, "Математика") in got and (0, 2, BOTH, "Физика") in got
    assert (2, 1, BOTH, "Информатика") in got                 # same number, other shift: no clash
    assert (2, 2, UPPER, "Химия") in got and not any(x.subject == "-" for x in lessons)
    assert (1, 3, UPPER, "Био") in got and (2, 3, LOWER, "Гео") in got


def test_parse_day_shift_clash_only_within_same_shift():
    assert logic.parse_day("1 [2см] A\n1 [2см] B")[1]
    assert not logic.parse_day("1 [1см] A\n1 [2см] B")[1]


def test_day_roundtrip_with_shifts():
    text = (
        "1 Математика, 301\n"
        "2 Физика\n"
        "1 [2см] Информатика, 112\n"
        "2 [2см] в: Химия / н: Гео"
    )
    lessons, errors = logic.parse_day(text)
    assert not errors
    assert logic.format_day(lessons) == text


def test_build_week_mixed_shifts_use_own_bells():
    def L(number, subject, shift=0):
        return logic.Lesson(number=number, week=BOTH, subject=subject, day=0, shift=shift)

    bells = {1: {1: logic.Bell(1, "08:30", "10:00"), 2: logic.Bell(2, "10:10", "11:40"), 3: logic.Bell(3, "11:50", "13:20")},
             2: {1: logic.Bell(1, "13:30", "15:00"), 2: logic.Bell(2, "15:10", "16:40")}}
    # three lessons in the first shift + one right after them in the second
    day = logic.build_week([L(1, "A"), L(2, "B"), L(3, "C"), L(1, "D", 2)], UPPER, {0: bells}, default_shift=1)[0]
    assert [(r.subject, r.time) for r in day.rows] == [
        ("A", "08:30–10:00"), ("B", "10:10–11:40"), ("C", "11:50–13:20"), ("D", "13:30–15:00")]

    # one lesson in the first shift, the rest in the second (default = 2); order follows the shifts
    day = logic.build_week([L(1, "A", 1), L(1, "B"), L(2, "C")], UPPER, {0: bells}, default_shift=2)[0]
    assert [(r.subject, r.time) for r in day.rows] == [
        ("A", "08:30–10:00"), ("B", "13:30–15:00"), ("C", "15:10–16:40")]

    # two + two; default shift is not set: only lessons with an explicit shift get a time
    day = logic.build_week([L(1, "A", 1), L(2, "B", 1), L(1, "C", 2), L(2, "D", 2)], UPPER, {0: bells})[0]
    assert [r.time for r in day.rows] == ["08:30–10:00", "10:10–11:40", "13:30–15:00", "15:10–16:40"]
    day = logic.build_week([L(1, "A"), L(1, "B", 2)], UPPER, {0: bells})[0]
    assert [(r.subject, r.time) for r in day.rows] == [("A", ""), ("B", "13:30–15:00")]


def test_count_lessons():
    ls = [logic.Lesson(1, UPPER, "A", day=0), logic.Lesson(1, LOWER, "B", day=0),
          logic.Lesson(1, BOTH, "C", day=0, shift=2), logic.Lesson(1, BOTH, "D", day=1)]
    assert logic.count_lessons(ls) == 3
