"""Клиент к любому OpenAI-совместимому API (Groq, OpenRouter, Gemini-compat, Mistral и т.д.)."""
from __future__ import annotations

import logging
import time

import aiohttp

from config import config

log = logging.getLogger(__name__)

_session: aiohttp.ClientSession | None = None
_blocked_until = 0.0  # после 429 не долбим API, пока не пройдёт пауза


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25))
    return _session


async def close() -> None:
    if _session is not None and not _session.closed:
        await _session.close()


async def complete(messages: list[dict[str, str]]) -> str | None:
    """Текст ответа модели или None при любой ошибке (бот просто промолчит)."""
    global _blocked_until
    if time.monotonic() < _blocked_until:
        return None
    payload = {
        "model": config.ai_model,
        "messages": messages,
        "max_tokens": config.ai_max_tokens,
        "temperature": 1.0,
    }
    headers = {"Authorization": f"Bearer {config.ai_api_key}"}
    try:
        http = await _get_session()
        async with http.post(f"{config.ai_base_url}/chat/completions", json=payload, headers=headers) as resp:
            if resp.status == 429:
                _blocked_until = time.monotonic() + 60
                log.warning("AI: лимит запросов (429), пауза 60 с")
                return None
            if resp.status != 200:
                log.warning("AI: HTTP %s: %s", resp.status, (await resp.text())[:200])
                return None
            data = await resp.json()
        return data["choices"][0]["message"]["content"]
    except (aiohttp.ClientError, TimeoutError, KeyError, IndexError, ValueError) as exc:
        log.warning("AI: ошибка запроса: %s", exc)
        return None
