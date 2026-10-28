"""Message rendering: a rich message with real tables, plus a plain-HTML fallback of the same content.

Rich messages need aiogram >= 3.31 (Bot API 10.x). On an older aiogram `RICH_AVAILABLE` is False and
every view only carries the HTML text, so the plugin still works (monospace tables in <pre>).
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any

from config import config
from utils.schedule.schedule_logic import DayView, build_bell_groups, text_table

try:
    from aiogram.types import (
        InputRichBlockParagraph,
        InputRichBlockSectionHeading,
        InputRichBlockTable,
        InputRichMessage,
        Message,
        RichBlockTableCell,
        RichTextBold,
        RichTextItalic,
        RichTextCustomEmoji,
    )

    RICH_AVAILABLE = hasattr(Message, "answer_rich")
except ImportError:  # old aiogram: no rich message types
    RICH_AVAILABLE = False


@dataclass
class View:
    rich: Any | None   # InputRichMessage, or None when rich messages are unavailable
    html: str          # always present: fallback text (HTML parse mode)


def _cell(text: Any, *, header: bool = False, align: str = "left") -> "RichBlockTableCell":
    # An omitted text makes the cell empty; an empty string is not guaranteed to be accepted.
    return RichBlockTableCell(
        align=align, valign="middle", text=text if text != "" else None, is_header=True if header else None
    )


def _table(header: list[str], rows: list[list[Any]], aligns: list[str]) -> "InputRichBlockTable":
    cells = [[_cell(h, header=True, align="center") for h in header]]
    cells += [[_cell(value, align=aligns[i]) for i, value in enumerate(row)] for row in rows]
    return InputRichBlockTable(cells=cells, is_bordered=True, is_compact=True)


# bells
def bells_view(by_day: dict) -> View:
    """Bell tables: one per group of weekdays that share the same bells (just one if no day differs)."""
    groups = build_bell_groups(by_day)
    title = "Расписание звонков"
    rich_title = [RichTextCustomEmoji(custom_emoji_id=config.icons["bells"], alternative_text="🔔"), " Расписание звонков"] if RICH_AVAILABLE else title
    html_title = f"<tg-emoji emoji-id=\"{config.icons['bells']}\">🔔</tg-emoji> {title}"
    if not groups:
        empty = "Расписание звонков ещё не заполнено."
        rich = None
        if RICH_AVAILABLE:
            rich = InputRichMessage(blocks=[
                InputRichBlockSectionHeading(text=rich_title, size=2),
                InputRichBlockParagraph(text=empty),
            ])
        return View(rich=rich, html=f"<b>{html_title}</b>\n\n{empty}")

    header = ["№", "1 смена", "2 смена"]
    html_parts = [f"<b>{html_title}</b>"]
    blocks: list[Any] = [InputRichBlockSectionHeading(text=rich_title, size=2)] if RICH_AVAILABLE else []
    for days_title, rows in groups:
        if days_title:
            html_parts.append(f"\n<b>{escape(days_title)}</b>")
            if RICH_AVAILABLE:
                blocks.append(InputRichBlockSectionHeading(text=days_title, size=4))
        else:
            html_parts.append("")
        html_parts.append(f"<pre>{text_table(header, rows)}</pre>")
        if RICH_AVAILABLE:
            blocks.append(_table(header, rows, ["center", "center", "center"]))
    rich = InputRichMessage(blocks=blocks) if RICH_AVAILABLE else None
    return View(rich=rich, html="\n".join(html_parts))


# week
def week_view(days: list[DayView], *, subtitle: str, note: str = "", show_time: bool = False) -> View:
    """Weekly timetable: one heading + one table per day.

    `subtitle` e.g. «Верхняя неделя · 12–18 октября»; `note` is an optional extra line.
    """
    title = "Расписание занятий"
    rich_title = [RichTextCustomEmoji(custom_emoji_id=config.icons["lessons"], alternative_text="📚"), " Расписание занятий"] if RICH_AVAILABLE else title
    html_title = f"<tg-emoji emoji-id=\"{config.icons['lessons']}\">📚</tg-emoji> {title}"
    has_room = any(row.room for day in days for row in day.rows)

    header = ["№"] + (["Время"] if show_time else []) + ["Предмет"] + (["Каб."] if has_room else [])
    aligns = ["center"] + (["center"] if show_time else []) + ["left"] + (["center"] if has_room else [])

    html_parts = [f"<b>{html_title}</b>", f"<b>{escape(subtitle)}</b>"]
    if note:
        html_parts.append(escape(note))
    blocks: list[Any] = []
    if RICH_AVAILABLE:
        blocks = [
            InputRichBlockSectionHeading(text=rich_title, size=2),
            InputRichBlockParagraph(text=RichTextBold(text=subtitle)),
        ]
        if note:
            blocks.append(InputRichBlockParagraph(text=note))

    for day in days:
        if RICH_AVAILABLE:
            blocks.append(InputRichBlockSectionHeading(text=day.title, size=4))
        if not day.rows:
            html_parts.append(f"\n<b>{escape(day.title)}</b>\nзанятий нет")
            if RICH_AVAILABLE:
                blocks.append(InputRichBlockParagraph(text="Занятий нет"))
            continue

        text_rows: list[list[str]] = []
        rich_rows: list[list[Any]] = []
        for row in day.rows:
            subject_text = row.subject + (f" — {row.teacher}" if row.teacher else "")
            text_row = [str(row.number)] + ([row.time or "—"] if show_time else []) + [subject_text]
            rich_subject: Any = (
                [f"{row.subject} ", RichTextItalic(text=row.teacher)] if row.teacher and RICH_AVAILABLE
                else row.subject
            )
            rich_row = [str(row.number)] + ([row.time or "—"] if show_time else []) + [rich_subject]
            if has_room:
                text_row.append(row.room or "")
                rich_row.append(row.room or "")
            text_rows.append(text_row)
            rich_rows.append(rich_row)
        html_parts.append(f"\n<b>{escape(day.title)}</b>\n<pre>{text_table(header, text_rows)}</pre>")
        if RICH_AVAILABLE:
            blocks.append(_table(header, rich_rows, aligns))

    rich = InputRichMessage(blocks=blocks) if RICH_AVAILABLE else None
    return View(rich=rich, html="\n".join(html_parts))
