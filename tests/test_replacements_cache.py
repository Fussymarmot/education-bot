import asyncio
from datetime import date

from utils.replacements import replacements_logic as lg
from utils.replacements.replacements_cache import FetchResult, ReplacementsCache


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Site:
    """Scripted fake of the college site."""

    def __init__(self):
        self.calls = []
        self.body = "v1"
        self.etag = None
        self.fail = False
        self.delay = 0

    async def __call__(self, etag, last_modified):
        self.calls.append((etag, last_modified))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise ConnectionError("down")
        if etag and etag == self.etag:
            return FetchResult(304, etag=etag)
        return FetchResult(200, self.body, etag=self.etag)


def make(site, clock, parse_log=None):
    def parse(body):
        if parse_log is not None:
            parse_log.append(body)
        return [lg.Replacement(date(2026, 10, 16), "I смена", lg.normalize_cells([body, "1"]))]

    return ReplacementsCache(site, parse, ttl=300, min_refresh=30, stale_ttl=3600, clock=clock)


def run(coro):
    return asyncio.run(coro)


def test_ttl_serves_from_cache_then_refreshes():
    site, clock = Site(), Clock()
    cache = make(site, clock)

    async def go():
        await cache.get()
        await cache.get()
        assert len(site.calls) == 1
        clock.now += 301
        await cache.get()
        assert len(site.calls) == 2

    run(go())


def test_force_is_throttled_by_min_refresh():
    site, clock = Site(), Clock()
    cache = make(site, clock)

    async def go():
        await cache.get()
        await cache.get(force=True)
        assert len(site.calls) == 1          # too soon
        clock.now += 31
        await cache.get(force=True)
        assert len(site.calls) == 2

    run(go())


def test_conditional_request_and_304_keeps_data():
    site, clock = Site(), Clock()
    site.etag = '"abc"'
    parsed = []
    cache = make(site, clock, parsed)

    async def go():
        first = await cache.get()
        clock.now += 400
        second = await cache.get()
        assert site.calls[1][0] == '"abc"'
        assert second.items == first.items and second.fetched_at > first.fetched_at
        assert parsed == ["v1"]              # not parsed twice

    run(go())


def test_identical_body_without_etag_is_not_reparsed():
    site, clock = Site(), Clock()
    parsed = []
    cache = make(site, clock, parsed)

    async def go():
        await cache.get()
        clock.now += 400
        await cache.get()
        assert len(site.calls) == 2 and parsed == ["v1"]
        site.body = "v2"
        clock.now += 400
        snap = await cache.get()
        assert parsed == ["v1", "v2"] and snap.items[0].group == "v2"

    run(go())


def test_concurrent_callers_share_one_request():
    site, clock = Site(), Clock()
    site.delay = 0.05
    cache = make(site, clock)

    async def go():
        await asyncio.gather(*(cache.get() for _ in range(10)))
        assert len(site.calls) == 1

    run(go())


def test_stale_on_error_then_recovery_and_no_retry_storm():
    site, clock = Site(), Clock()
    cache = make(site, clock)

    async def go():
        await cache.get()
        site.fail = True
        clock.now += 400
        snap = await cache.get()
        assert snap.stale and snap.error and len(site.calls) == 2
        await cache.get()                    # within min_refresh of the failure: no new attempt
        assert len(site.calls) == 2
        clock.now += 31
        site.fail = False
        snap = await cache.get()
        assert not snap.stale and len(site.calls) == 3

    run(go())


def test_error_without_cached_data_raises_and_too_old_data_is_not_served():
    site, clock = Site(), Clock()
    cache = make(site, clock)
    site.fail = True

    async def go():
        try:
            await cache.get()
        except ConnectionError:
            pass
        else:
            raise AssertionError("expected an error")
        site.fail = False
        await cache.get()
        site.fail = True
        clock.now += 3601 + 31
        try:
            await cache.get()
        except ConnectionError:
            return
        raise AssertionError("data older than stale_ttl must not be served")

    run(go())
