"""Database engine and session management."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import config
from database.models import Base

engine = create_async_engine(config.database_url)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session() -> AsyncIterator[AsyncSession]:
    """Write session: commits on clean exit, rolls back on error."""
    async with session_factory.begin() as s:
        yield s


@asynccontextmanager
async def read_session() -> AsyncIterator[AsyncSession]:
    """Read-only session."""
    async with session_factory() as s:
        yield s


def _migrate_lessons_shift(conn) -> None:
    """Old `schedule_lessons` has no `shift` column and a unique key without it: add both, keep the data."""
    from sqlalchemy import inspect, text

    inspector = inspect(conn)
    if "schedule_lessons" not in inspector.get_table_names():
        return
    if any(c["name"] == "shift" for c in inspector.get_columns("schedule_lessons")):
        return
    if conn.dialect.name == "sqlite":      # SQLite cannot change a constraint: rebuild the table
        conn.execute(text("ALTER TABLE schedule_lessons RENAME TO schedule_lessons_old"))
        Base.metadata.tables["schedule_lessons"].create(conn)
        conn.execute(text(
            "INSERT INTO schedule_lessons (id, day, number, week, shift, subject, room, teacher) "
            "SELECT id, day, number, week, 0, subject, room, teacher FROM schedule_lessons_old"
        ))
        conn.execute(text("DROP TABLE schedule_lessons_old"))
    else:
        conn.execute(text("ALTER TABLE schedule_lessons ADD COLUMN shift INTEGER NOT NULL DEFAULT 0"))
        conn.execute(text("ALTER TABLE schedule_lessons DROP CONSTRAINT IF EXISTS uq_schedule_lessons_slot"))
        conn.execute(text("ALTER TABLE schedule_lessons ADD CONSTRAINT uq_schedule_lessons_slot "
                          "UNIQUE (day, shift, number, week)"))


async def init_db() -> None:
    """Create missing tables and upgrade the lessons table of an older database."""
    async with engine.begin() as conn:
        await conn.run_sync(_migrate_lessons_shift)
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()
