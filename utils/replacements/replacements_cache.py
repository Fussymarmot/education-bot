"""In-process cache for the replacements page.

* TTL: repeated commands within `ttl` seconds never touch the college site.
* Conditional requests: ETag / Last-Modified are sent back, a 304 only refreshes the timestamp.
* Parse once: an unchanged body is not parsed again (BeautifulSoup runs off the event loop).
* Single flight: concurrent callers share one request instead of each hitting the site.
* Stale-on-error: if the site is down, the last good data (up to `stale_ttl`) is served, flagged `stale`.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, replace
from typing import Awaitable, Callable

from utils.replacements.replacements_logic import Replacement

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FetchResult:
    status: int                      # 200 or 304
    body: str | None = None
    etag: str | None = None
    last_modified: str | None = None


@dataclass(frozen=True)
class Snapshot:
    items: tuple[Replacement, ...]
    fetched_at: float                # when the data was last confirmed by the site (epoch seconds)
    stale: bool = False              # True: the site could not be reached, this is older data
    error: str | None = None


Fetcher = Callable[[str | None, str | None], Awaitable[FetchResult]]
Parser = Callable[[str], list[Replacement]]


class ReplacementsCache:
    def __init__(
        self,
        fetch: Fetcher,
        parse: Parser,
        *,
        ttl: float = 300,
        min_refresh: float = 30,
        stale_ttl: float = 6 * 3600,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._fetch = fetch
        self._parse = parse
        self.ttl = ttl
        self.min_refresh = min_refresh
        self.stale_ttl = stale_ttl
        self._clock = clock
        self._lock = asyncio.Lock()
        self._snapshot: Snapshot | None = None
        self._etag: str | None = None
        self._last_modified: str | None = None
        self._body_hash: str | None = None
        self._failed_at: float | None = None

    @property
    def snapshot(self) -> Snapshot | None:
        return self._snapshot

    def _fresh_enough(self, max_age: float) -> bool:
        snap = self._snapshot
        if snap is None:
            return False
        now = self._clock()
        if snap.stale:
            # The last attempt failed: do not retry on every command (each try can take the full
            # timeout), wait `min_refresh` first.
            return self._failed_at is not None and now - self._failed_at < self.min_refresh
        return now - snap.fetched_at < max_age

    async def get(self, *, force: bool = False) -> Snapshot:
        """Return current data. `force` asks for a re-check, but never more often than `min_refresh`,
        so a refresh button cannot be used to hammer the site."""
        max_age = self.min_refresh if force else self.ttl
        if self._fresh_enough(max_age):
            return self._snapshot  # type: ignore[return-value]
        async with self._lock:
            if self._fresh_enough(max_age):   # somebody else refreshed while we waited
                return self._snapshot         # type: ignore[return-value]
            return await self._refresh()

    async def _refresh(self) -> Snapshot:
        now = self._clock()
        try:
            result = await self._fetch(self._etag, self._last_modified)
            if result.status == 304 and self._snapshot is not None:
                self._snapshot = replace(self._snapshot, fetched_at=now, stale=False, error=None)
                self._failed_at = None
                return self._snapshot
            if result.body is None:
                raise ValueError(f"empty response (status {result.status})")
            digest = hashlib.sha1(result.body.encode("utf-8", errors="replace")).hexdigest()
            if digest == self._body_hash and self._snapshot is not None:
                items = self._snapshot.items            # identical page: skip parsing
            else:
                items = tuple(await asyncio.to_thread(self._parse, result.body))
            self._etag, self._last_modified, self._body_hash = result.etag, result.last_modified, digest
            self._snapshot = Snapshot(items=items, fetched_at=now)
            self._failed_at = None
            return self._snapshot
        except Exception as exc:
            snap = self._snapshot
            self._failed_at = now
            if snap is not None and now - snap.fetched_at <= self.stale_ttl:
                log.warning("Replacements site unavailable, serving cached data: %s", exc)
                self._snapshot = replace(snap, stale=True, error=str(exc)[:200])
                return self._snapshot
            raise
