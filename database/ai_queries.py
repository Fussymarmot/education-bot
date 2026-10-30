"""Память ИИ-собеседника: запись сообщений, выдача контекста, автоочистка."""
from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import delete, or_, select

from database.engine import read_session, session
from database.models import AiMessage

MAX_LEN = 400  # длиннее в память не кладём - экономим токены


@dataclass(frozen=True)
class Line:
    role: str
    author: str
    content: str
    user_id: int | None = None


async def add_message(chat_id: int, user_id: int | None, role: str, author: str, content: str,
                      *, keep: int, ttl_hours: float, now: float | None = None) -> None:
    """Сохранить сообщение и сразу подчистить: оставляем последние `keep` и не старше `ttl_hours`."""
    now = time.time() if now is None else now
    content = content.strip()[:MAX_LEN]
    if not content:
        return
    async with session() as s:
        s.add(AiMessage(chat_id=chat_id, user_id=user_id, role=role,
                        author=author[:64] or "?", content=content, created_at=now))
        await s.flush()
        newest = select(AiMessage.id).where(AiMessage.chat_id == chat_id).order_by(AiMessage.id.desc()).limit(keep)
        await s.execute(delete(AiMessage).where(
            AiMessage.chat_id == chat_id,
            or_(AiMessage.created_at < now - ttl_hours * 3600, AiMessage.id.not_in(newest)),
        ))


async def get_context(chat_id: int, limit: int) -> list[Line]:
    """Последние сообщения чата в хронологическом порядке."""
    async with read_session() as s:
        rows = (await s.scalars(
            select(AiMessage).where(AiMessage.chat_id == chat_id).order_by(AiMessage.id.desc()).limit(limit)
        )).all()
    return [Line(r.role, r.author, r.content, r.user_id) for r in reversed(rows)]


async def clear_chat(chat_id: int) -> None:
    async with session() as s:
        await s.execute(delete(AiMessage).where(AiMessage.chat_id == chat_id))
