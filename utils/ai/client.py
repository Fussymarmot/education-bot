"""Клиент к OpenAI-совместимому API: Cloudflare Workers AI, Groq, OpenRouter, Mistral и т.д."""
from __future__ import annotations

import logging
import time
from typing import Any

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


def endpoint() -> str:
    """URL chat/completions. Если задан AI_CF_ACCOUNT_ID - берём OpenAI-совместимый эндпоинт Cloudflare Workers AI."""
    if config.ai_cf_account_id:
        return (f"https://api.cloudflare.com/client/v4/accounts/{config.ai_cf_account_id}"
                "/ai/v1/chat/completions")
    return f"{config.ai_base_url}/chat/completions"


def extract_text(data: Any) -> str | None:
    """Достаёт текст ответа из разных форматов: OpenAI, нативный Cloudflare (`result.response`), Responses API.

    Поля с рассуждениями (reasoning) намеренно игнорируем - в чат они попадать не должны.
    """
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("result"), dict):          # нативный ответ Cloudflare: {"result": {...}, "success": true}
        data = data["result"]
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):                  # content-части: [{"type": "text", "text": "..."}]
            return "".join(p.get("text", "") for p in content if isinstance(p, dict)) or None
        return choices[0].get("text") if isinstance(choices[0].get("text"), str) else None
    if isinstance(data.get("response"), str):          # {"response": "..."}
        return data["response"]
    output = data.get("output")                        # формат Responses API (gpt-oss на Cloudflare)
    if isinstance(output, list):
        parts = [c.get("text", "")
                 for item in output if isinstance(item, dict) and item.get("type") == "message"
                 for c in item.get("content") or [] if isinstance(c, dict) and c.get("type") == "output_text"]
        return "".join(parts) or None
    return None


async def complete(messages: list[dict[str, str]]) -> str | None:
    """Текст ответа модели или None при любой ошибке (бот просто промолчит)."""
    global _blocked_until
    if time.monotonic() < _blocked_until:
        return None
    payload = {
        "model": config.ai_model,
        "messages": messages,
        "max_tokens": config.ai_max_tokens,
        "temperature": config.ai_temperature,
    }
    headers = {"Authorization": f"Bearer {config.ai_api_key}"}
    try:
        http = await _get_session()
        async with http.post(endpoint(), json=payload, headers=headers) as resp:
            if resp.status == 429:
                _blocked_until = time.monotonic() + 60
                log.warning("AI: лимит запросов (429), пауза 60 с")
                return None
            if resp.status != 200:
                log.warning("AI: HTTP %s: %s", resp.status, (await resp.text())[:300])
                return None
            data = await resp.json(content_type=None)
        if isinstance(data, dict) and data.get("success") is False:
            log.warning("AI: ошибка Cloudflare: %s", str(data.get("errors"))[:300])
            return None
        text = extract_text(data)
        if text is None:
            log.warning("AI: непонятный формат ответа: %s", str(data)[:300])
        return text
    except (aiohttp.ClientError, TimeoutError, KeyError, IndexError, ValueError, AttributeError) as exc:
        log.warning("AI: ошибка запроса: %s", exc)
        return None
