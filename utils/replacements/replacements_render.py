"""Rendering: rich-message tables (when aiogram supports them) with an HTML fallback, plus change digests."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, tzinfo
from html import escape
from typing import Iterable, Sequence

from config import config
from utils.replacements.replacements_logic import ADDED, CHANGED, DAY_ABBR, HEADER, REMOVED, Change, Replacement

try:
    from aiogram.types import (
        InputRichBlockParagraph, InputRichBlockSectionHeading, InputRichBlockTable,
        InputRichMessage, Message as AiogramMessage, RichBlockTableCell, RichTextCustomEmoji,
    )
    RICH_AVAILABLE = hasattr(AiogramMessage, "answer_rich")
except ImportError:
    RICH_AVAILABLE = False

TITLE = "Замены в расписании"
TITLE_EMOJI_ID = config.icons["replacements"]
WARNING_EMOJI_ID = config.icons["warning"]
DAY_EMOJI_ID = config.icons["calendar"]
HTML_LIMIT = 3800


def _rich_emoji(emoji_id: str, alternative_text: str, text: str = "") -> list:
    """Build rich-text content; never put Telegram HTML tags inside rich blocks."""
    return [RichTextCustomEmoji(custom_emoji_id=emoji_id, alternative_text=alternative_text), text]


def _html_emoji(key: str, fallback: str) -> str:
    """HTML fallback only. Rich-message blocks use RichTextCustomEmoji instead."""
    emoji_id = config.icons.get(key, "")
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>' if emoji_id else fallback


def _rich_meta(fetched_at: float | None, stale: bool, tz: tzinfo | None):
    if fetched_at is None or tz is None:
        return ""
    stamp = datetime.fromtimestamp(fetched_at, tz).strftime("%d.%m %H:%M")
    if stale:
        return _rich_emoji(WARNING_EMOJI_ID, "⚠️", f" Сайт недоступен, данные от {stamp} (МСК)")
    return f"Обновлено {stamp} (МСК)"


@dataclass(frozen=True)
class View:
    rich: object | None          # InputRichMessage or None when rich messages are unavailable
    html: tuple[str, ...]        # one or more HTML messages (the fallback, split by the size limit)


# small helpers
def day_label(day: date) -> str:
    return f"{day.strftime('%d.%m.%Y')} ({DAY_ABBR[day.weekday()]})"


def _lesson_label(lesson: str) -> str:
    return f"{lesson} пара" if re.fullmatch(r"[\d,\-–\s]+", lesson) else lesson


def _details(r: Replacement) -> str:
    parts = [r.subject, f"каб. {r.room}" if r.room else "", r.teacher]
    return " · ".join(p for p in parts if p) or "—"


def row_html(r: Replacement) -> str:
    head = f"<b>{escape(r.group)}</b>"
    if r.lesson:
        head += f" · {escape(_lesson_label(r.lesson))}"
    return f"{head}\n└ {escape(_details(r))}"


def _pack(title_lines: Sequence[str], sections: Sequence[tuple[str, Sequence[str]]], limit: int = HTML_LIMIT) -> tuple[str, ...]:
    """Pack sections (heading + rows) into messages <= limit characters. Rows are never split; a day that
    continues in the next message gets its heading repeated."""
    chunks: list[str] = []
    cur: list[str] = list(title_lines)
    size = sum(len(x) + 1 for x in cur)
    for heading, rows in sections:
        opened = False
        for row in rows:
            cost = len(row) + 2 + (0 if opened else len(heading) + 2)
            has_sections = opened or len(cur) > len(title_lines) or chunks
            if size + cost > limit and cur and has_sections:
                chunks.append("\n".join(cur))
                cur, size, opened = [], 0, False
                cost = len(row) + 2 + len(heading) + 2
            if not opened:
                cur.append(f"\n{heading}")
                size += len(heading) + 2
                opened = True
            cur.append(row)
            size += len(row) + 1
    if cur:
        chunks.append("\n".join(cur))
    return tuple(chunks)


def _meta(fetched_at: float | None, stale: bool, tz: tzinfo | None) -> str:
    if fetched_at is None or tz is None:
        return ""
    stamp = datetime.fromtimestamp(fetched_at, tz).strftime("%d.%m %H:%M")
    return f"{_html_emoji('warning', '⚠️')} Сайт недоступен, данные от {stamp} (МСК)" if stale else f"Обновлено {stamp} (МСК)"


# the /replacements view
def _group(items: Iterable[Replacement]) -> dict[tuple[date, str], list[Replacement]]:
    grouped: dict[tuple[date, str], list[Replacement]] = {}
    for item in items:
        grouped.setdefault((item.date, item.shift), []).append(item)
    return grouped


def _make_table(rows: Sequence[Sequence[str]]):
    cells = [[RichBlockTableCell(text=x, is_header=True, align="center", valign="middle") for x in HEADER]]
    for row in rows:
        cells.append([
            RichBlockTableCell(text=(value or "—"), align="left", valign="middle") for value in row
        ])
    return InputRichBlockTable(cells=cells, is_bordered=True, is_compact=True)


def build_view(
    items: Sequence[Replacement],
    today: date,
    *,
    group: str | None = None,
    fetched_at: float | None = None,
    stale: bool = False,
    tz: tzinfo | None = None,
    source_url: str = "",
) -> View:
    """`items` must already be filtered to upcoming dates (and to the group, if any)."""
    meta = _meta(fetched_at, stale, tz)
    title = TITLE + (f" · {group}" if group else "")
    rich_title = _rich_emoji(TITLE_EMOJI_ID, "🔄", f" {title[len('Замены в расписании'):] if group else TITLE}")
    link = f'Источник: <a href="{escape(source_url)}">сайт колледжа</a>' if source_url else ""
    head_html = [f"<b>{_html_emoji('replacements', '🔄')} {escape(title)}</b>"] + [x for x in (meta if meta else "", link) if x]

    grouped = _group(items)
    if not grouped:
        who = f" для группы {group}" if group else ""
        msg = f"На {today.strftime('%d.%m.%Y')} и будущие даты замен{who} на сайте не найдено."
        rich = None
        if RICH_AVAILABLE:
            blocks = [InputRichBlockSectionHeading(text=rich_title, size=2)]
            rich_meta = _rich_meta(fetched_at, stale, tz)
            if rich_meta:
                blocks.append(InputRichBlockParagraph(text=rich_meta))
            blocks.append(InputRichBlockParagraph(text=msg))
            rich = InputRichMessage(blocks=blocks)
        return View(rich, ("\n".join(head_html + ["", escape(msg)]),))

    sections = []
    blocks = []
    if RICH_AVAILABLE:
        blocks.append(InputRichBlockSectionHeading(text=rich_title, size=2))
        rich_meta = _rich_meta(fetched_at, stale, tz)
        if rich_meta:
            blocks.append(InputRichBlockParagraph(text=rich_meta))
    for (day, shift), rows in grouped.items():
        heading = f"{day_label(day)} · {shift}"
        sections.append((f"<b>{_html_emoji('calendar', '📆')} {escape(heading)}</b>", [row_html(r) for r in rows]))
        if RICH_AVAILABLE:
            blocks.append(InputRichBlockSectionHeading(
                text=_rich_emoji(DAY_EMOJI_ID, "📆", f" {heading}"), size=3
            ))
            blocks.append(_make_table([r.cells for r in rows]))
    rich = InputRichMessage(blocks=blocks) if RICH_AVAILABLE else None
    return View(rich, _pack(head_html, sections))


# change digest
def _change_html(change: Change) -> str:
    if change.kind == ADDED:
        return f"{_html_emoji('added', '➕')} " + row_html(change.new)
    if change.kind == REMOVED:
        o = change.old
        return f"{_html_emoji('removed', '➖')} <s>{escape(o.group)}"+(f" · {escape(_lesson_label(o.lesson))}" if o.lesson else "")+f"</s>\n└ <s>{escape(_details(o))}</s>"
    n, o = change.new, change.old
    head = f"{_html_emoji('changed', '✏️')} <b>{escape(n.group)}</b>" + (f" · {escape(_lesson_label(n.lesson))}" if n.lesson else "")
    return f"{head}\n└ было: <s>{escape(_details(o))}</s>\n└ стало: {escape(_details(n))}"


def format_changes(changes: Sequence[Change], *, source_url: str = "") -> tuple[str, ...]:
    """HTML digest of what changed on the site since the last check."""
    counts = {k: sum(1 for c in changes if c.kind == k) for k in (ADDED, CHANGED, REMOVED)}
    summary = ", ".join(
        f"{label} {counts[kind]}"
        for kind, label in ((ADDED, "новых"), (CHANGED, "изменено"), (REMOVED, "отменено"))
        if counts[kind]
    )
    title = [f"{_html_emoji('bells', '🔔')} <b>Изменения в заменах</b>", escape(summary)]
    if source_url:
        title.append(f'<a href="{escape(source_url)}">Открыть сайт колледжа</a>')
    sections: dict[tuple[date, str], list[str]] = {}
    for change in changes:
        ref = change.ref
        sections.setdefault((ref.date, ref.shift), []).append(_change_html(change))
    packed = [(f"<b>{_html_emoji('calendar', '📅')} {escape(day_label(d))} · {escape(shift)}</b>", rows) for (d, shift), rows in sections.items()]
    return _pack(title, packed)
