"""Pure logic of the replacements plugin: parsing, normalisation, diffing.

Nothing here imports aiogram or SQLAlchemy, so it is cheap to unit-test and safe to reuse.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Sequence

MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5,
    "июня": 6, "июля": 7, "августа": 8, "сентября": 9,
    "октября": 10, "ноября": 11, "декабря": 12,
}
DATE_RE = re.compile(
    r"(?:ИЗМЕНЕНИ[ЕЯ]\s+В\s+РАСПИСАНИИ\s+НА\s*)?"
    r"(\d{1,2})\s+([А-ЯЁа-яё]+)\s+(\d{4})\s*года?",
    re.IGNORECASE,
)

COLUMNS = 5  # group, lesson, subject, room, teacher
HEADER = ("Группа", "Урок", "Дисциплина", "Кабинет", "Преподаватель")
SHIFT_UNKNOWN = "Смена не указана"
SHIFT_ORDER = {"I смена": 1, "II смена": 2, SHIFT_UNKNOWN: 3}
DAY_ABBR = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
MAX_GROUP_FILTER = 20  # also bounds callback_data size

# If the site suddenly returns no upcoming replacements while we know some, we do not believe it
# right away (broken page, layout change): the drop has to be seen this many checks in a row.
EMPTY_CONFIRMATIONS = 3


# --------------------------------------------------------------------------- model
def _squash(text: str) -> str:
    return " ".join(str(text).replace("\xa0", " ").split())


def _fold(text: str) -> str:
    return _squash(text).casefold().replace("ё", "е")


def normalize_cells(cells: Iterable[str]) -> tuple[str, ...]:
    """Exactly COLUMNS cells: extra cells are merged into the last column, missing ones are empty."""
    values = [_squash(c) for c in cells]
    if len(values) > COLUMNS:
        values = values[: COLUMNS - 1] + [" ".join(v for v in values[COLUMNS - 1:] if v)]
    values += [""] * (COLUMNS - len(values))
    return tuple(values)


@dataclass(frozen=True)
class Replacement:
    date: date
    shift: str
    cells: tuple[str, ...]

    @property
    def group(self) -> str:
        return self.cells[0]

    @property
    def lesson(self) -> str:
        return self.cells[1]

    @property
    def subject(self) -> str:
        return self.cells[2]

    @property
    def room(self) -> str:
        return self.cells[3]

    @property
    def teacher(self) -> str:
        return self.cells[4]

    @property
    def key(self) -> tuple[date, str, str]:
        """Identity of a slot. The shift is deliberately NOT part of it: it is only a heading on the
        site, and a heading that appears or changes must not look like every lesson was replaced."""
        return (self.date, _slot_key(self.group), _slot_key(self.lesson))

    @property
    def fingerprint(self) -> str:
        raw = "\x1f".join(_fold(c) for c in self.cells)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    @property
    def sort_key(self) -> tuple:
        return (self.date, SHIFT_ORDER.get(self.shift, 3), _fold(self.group), _fold(self.lesson))


def _slot_key(text: str) -> str:
    return re.sub(r"[\s.\-_,()]", "", _fold(text))


# parsing
def parse_date(text: str) -> date | None:
    match = DATE_RE.search(text)
    if not match:
        return None
    day, month, year = match.groups()
    month_num = MONTHS.get(month.lower())
    if not month_num:
        return None
    try:
        return date(int(year), month_num, int(day))
    except ValueError:
        return None


def detect_shift(text: str) -> str | None:
    upper = text.upper()
    if "СМЕНА" not in upper or len(text) >= 80:
        return None
    if "II СМЕНА" in upper or "2 СМЕНА" in upper or "ВТОРАЯ СМЕНА" in upper:
        return "II смена"
    if "I СМЕНА" in upper or "1 СМЕНА" in upper or "ПЕРВАЯ СМЕНА" in upper:
        return "I смена"
    return None


def _node_text(node) -> str:
    return _squash(node.get_text(" ", strip=True))


def parse_html(html: str) -> list[Replacement]:
    """Extract replacements from the page. Walks elements in document order (date -> shift -> table),
    so it does not depend on the CSS classes of the WordPress theme."""
    # Imported lazily so the bot still starts without bs4; the caller shows a clear error instead.
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    root = soup.find(id="content") or soup.find("article") or soup
    items: list[Replacement] = []
    current_date: date | None = None
    current_shift = SHIFT_UNKNOWN

    for node in root.find_all(["p", "h1", "h2", "h3", "h4", "strong", "b", "table"]):
        if node.name == "table":
            if current_date is None:
                continue
            rows = []
            for tr in node.find_all("tr"):
                cells = [_node_text(c) for c in tr.find_all(["th", "td"], recursive=False)]
                if not cells:
                    cells = [_node_text(c) for c in tr.find_all(["th", "td"])]
                cells = [c for c in cells if c]
                if cells:
                    rows.append(cells)
            if rows:
                header = [c.lower() for c in rows[0]]
                if any("групп" in c for c in header) and any("дисциплин" in c for c in header):
                    rows = rows[1:]  # a repeated header is not a data row
                for cells in rows:
                    if len(cells) >= 2 and not cells[0].lower().startswith("групп"):
                        items.append(Replacement(current_date, current_shift, normalize_cells(cells)))
            continue

        text = _node_text(node)
        found = parse_date(text)
        if found:
            current_date, current_shift = found, SHIFT_UNKNOWN
            continue
        shift = detect_shift(text)
        if shift:
            current_shift = shift
    return items


# filtering
def upcoming(items: Iterable[Replacement], today: date) -> list[Replacement]:
    return sorted((i for i in items if i.date >= today), key=lambda i: i.sort_key)


def clean_group(raw: str | None) -> str | None:
    """User-supplied group filter -> normalised string, or None for 'no filter'."""
    value = _squash(raw or "")
    return value[:MAX_GROUP_FILTER] or None


def matches_group(item: Replacement, group: str | None) -> bool:
    if not group:
        return True
    return _slot_key(group) in _slot_key(item.group)


def filter_group(items: Iterable[Replacement], group: str | None) -> list[Replacement]:
    return [i for i in items if matches_group(i, group)]


# snapshot (de)serialisation
def dump_snapshot(items: Iterable[Replacement]) -> str:
    rows = [[i.date.isoformat(), i.shift, *i.cells] for i in sorted(items, key=lambda i: i.sort_key)]
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def load_snapshot(raw: str | None) -> list[Replacement] | None:
    """None means 'no usable snapshot' (absent or corrupt) - the caller re-initialises silently."""
    if raw is None:
        return None
    try:
        return [
            Replacement(date.fromisoformat(row[0]), row[1], normalize_cells(row[2:]))
            for row in json.loads(raw)
        ]
    except (ValueError, TypeError, IndexError):
        return None


# diff
ADDED, CHANGED, REMOVED = "added", "changed", "removed"


@dataclass(frozen=True)
class Change:
    kind: str
    new: Replacement | None = None
    old: Replacement | None = None

    @property
    def ref(self) -> Replacement:
        return self.new or self.old  # type: ignore[return-value]


def diff_items(old: Sequence[Replacement], new: Sequence[Replacement]) -> list[Change]:
    """Compare two snapshots. Slots with several rows (subgroups, two teachers) are compared as
    multisets, so reordering rows on the page is not a change."""
    old_by_key: dict[tuple, list[Replacement]] = {}
    new_by_key: dict[tuple, list[Replacement]] = {}
    for item in old:
        old_by_key.setdefault(item.key, []).append(item)
    for item in new:
        new_by_key.setdefault(item.key, []).append(item)

    changes: list[Change] = []
    for key in old_by_key.keys() | new_by_key.keys():
        old_left = list(old_by_key.get(key, []))
        new_left: list[Replacement] = []
        for item in new_by_key.get(key, []):
            for index, candidate in enumerate(old_left):
                if candidate.fingerprint == item.fingerprint:
                    del old_left[index]
                    break
            else:
                new_left.append(item)
        paired = min(len(old_left), len(new_left))
        for o, n in zip(old_left[:paired], new_left[:paired]):
            changes.append(Change(CHANGED, new=n, old=o))
        changes.extend(Change(ADDED, new=n) for n in new_left[paired:])
        changes.extend(Change(REMOVED, old=o) for o in old_left[paired:])
    changes.sort(key=lambda c: (c.ref.sort_key, c.kind))
    return changes


@dataclass(frozen=True)
class Decision:
    action: str                           # init | hold | apply
    snapshot: list[Replacement] | None    # what to store; None = keep the stored one
    changes: list[Change]
    empty_streak: int


def plan_update(
    stored: list[Replacement] | None,
    fetched: Iterable[Replacement],
    today: date,
    empty_streak: int = 0,
    *,
    confirm_empty: int = EMPTY_CONFIRMATIONS,
) -> Decision:
    """Decide what a background check should do. Pure: the caller does the I/O.

    * no stored snapshot  -> `init`: remember the current state, notify nobody (no first-run blast);
    * page suddenly empty -> `hold` until the emptiness is confirmed several times in a row;
    * otherwise           -> `apply`: store the new snapshot and report the differences.
    """
    new = upcoming(fetched, today)
    if stored is None:
        return Decision("init", new, [], 0)
    old = upcoming(stored, today)
    if not new and old:
        streak = empty_streak + 1
        if streak < confirm_empty:
            return Decision("hold", None, [], streak)
    return Decision("apply", new, diff_items(old, new), 0)
