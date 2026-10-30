"""Упоминания людей: имена берём только из недавнего лога, в текст подставляем tg://user?id ссылки."""
from __future__ import annotations

import html
import re

from database.ai_queries import Line

MAX_MENTIONS = 2


def participants(history: list[Line]) -> dict[str, int]:
    """{имя: user_id} по недавним сообщениям. Одинаковые имена у разных людей выкидываем (кого звать - неясно)."""
    seen: dict[str, set[int]] = {}
    for line in history:
        if line.role == "user" and line.user_id is not None and line.author.strip():
            seen.setdefault(line.author.strip(), set()).add(line.user_id)
    return {name: next(iter(ids)) for name, ids in seen.items() if len(ids) == 1}


def render_mentions(text: str, people: dict[str, int], *, limit: int = MAX_MENTIONS) -> str:
    """Экранирует текст под parse_mode=HTML и превращает имена из `people` в упоминания (каждого максимум раз)."""
    out = html.escape(text, quote=False)
    done = 0
    for name in sorted(people, key=len, reverse=True):
        if done >= limit:
            break
        pattern = re.compile(rf"(?<!\w){re.escape(html.escape(name, quote=False))}(?!\w)", re.IGNORECASE)
        found = pattern.search(out)
        if found is None or "<a " in out[max(0, found.start() - 40):found.start()]:
            continue
        link = f'<a href="tg://user?id={people[name]}">{found.group(0)}</a>'
        out = out[:found.start()] + link + out[found.end():]
        done += 1
    return out
