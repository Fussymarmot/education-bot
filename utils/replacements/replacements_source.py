"""HTTP access to the college site (aiohttp is already a dependency of aiogram)."""
from __future__ import annotations

from utils.replacements.replacements_cache import FetchResult

URL = "https://shapt.ru/?page_id=18818"
USER_AGENT = "Mozilla/5.0 (compatible; ShaptScheduleBot/2.0)"
TIMEOUT_SECONDS = 20
MAX_BYTES = 5 * 1024 * 1024


async def fetch_page(etag: str | None = None, last_modified: str | None = None) -> FetchResult:
    import aiohttp

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(URL) as response:
            if response.status == 304:
                return FetchResult(304, etag=etag, last_modified=last_modified)
            response.raise_for_status()
            if (response.content_length or 0) > MAX_BYTES:
                raise ValueError("page is unexpectedly large")
            body = await response.text(errors="replace")
            return FetchResult(
                200, body,
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
            )
