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


async def init_db() -> None:
    """Create missing tables (leaves existing ones untouched)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()
