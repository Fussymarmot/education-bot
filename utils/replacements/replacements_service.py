"""Replacement fetching, caching, rendering, and notifications."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramMigrateToChat

from config import config
from database import queries
from utils.replacements import replacements_logic as rl
from utils.common.messaging import send_html
from utils.replacements.replacements_cache import ReplacementsCache, Snapshot
from utils.replacements.replacements_render import View, build_view, format_changes
from utils.replacements.replacements_source import URL, fetch_page

log = logging.getLogger(__name__)

STATE_SNAPSHOT = "snapshot"
STATE_EMPTY_STREAK = "empty_streak"
FIRST_CHECK_DELAY = 15

cache = ReplacementsCache(fetch_page, rl.parse_html, ttl=config.shapt_cache_ttl)


async def build(group: str | None, *, force: bool = False) -> View:
    snap: Snapshot = await cache.get(force=force)
    today = datetime.now(config.tz).date()
    items = rl.filter_group(rl.upcoming(snap.items, today), group)
    return build_view(items, today, group=group, fetched_at=snap.fetched_at, stale=snap.stale,
                      tz=config.tz, source_url=URL)


async def _notify(bot, changes: list[rl.Change]) -> None:
    """Send group changes to the work group if it's configured."""
    chat_id = config.group_chat_id
    group = await queries.get_replacements_group()
    if chat_id is None or group is None:
        return
    relevant = [c for c in changes if rl.matches_group(c.ref, group)]
    if not relevant:
        return
    try:
        await send_html(bot, chat_id, format_changes(relevant, source_url=URL))
    except TelegramMigrateToChat as exc:
        log.error("Group became a supergroup, new id: %s - update GROUP_CHAT_ID", exc.migrate_to_chat_id)
    except TelegramForbiddenError:
        log.error("Bot cannot write to group %s: removed or access denied", chat_id)
    except TelegramAPIError as exc:
        log.warning("Не удалось отправить изменения замен в группу %s: %s", chat_id, exc)
    else:
        log.info("Изменения замен (%s шт.) отправлены в группу, фильтр %s", len(relevant), group)


async def _check_once(bot) -> None:
    snap = await cache.get(force=True)
    if snap.stale:
        return   # the site is unreachable: nothing to learn
    today = datetime.now(config.tz).date()
    stored = rl.load_snapshot(await queries.get_state(STATE_SNAPSHOT))
    streak = int(await queries.get_state(STATE_EMPTY_STREAK) or 0)
    decision = rl.plan_update(stored, snap.items, today, streak)

    if decision.action == "hold":
        log.warning("Сайт вернул пустой список замен, хотя раньше они были (%s/%s) — жду подтверждения",
                    decision.empty_streak, rl.EMPTY_CONFIRMATIONS)
    if decision.empty_streak != streak:
        await queries.set_state(STATE_EMPTY_STREAK, str(decision.empty_streak))
    if decision.snapshot is not None:
        await queries.set_state(STATE_SNAPSHOT, rl.dump_snapshot(decision.snapshot))
    if decision.action == "init":
        log.info("Замены: первичный снимок сохранён (%s записей), уведомления не рассылаются",
                 len(decision.snapshot or []))
    if decision.changes:
        await _notify(bot, decision.changes)


async def poller(bot) -> None:
    """Background task: every SHAPT_POLL_INTERVAL seconds compares the site with the snapshot and sends the diff to the group."""
    await asyncio.sleep(FIRST_CHECK_DELAY)
    while True:
        try:
            await _check_once(bot)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if isinstance(exc, (OSError, asyncio.TimeoutError)) or type(exc).__module__.startswith("aiohttp"):
                log.warning("Проверка замен не удалась: %s", exc)
            else:
                log.exception("Проверка замен завершилась ошибкой")
        await asyncio.sleep(config.shapt_poll_interval)
