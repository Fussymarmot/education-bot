"""Configuration loaded from environment variables and .env file."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

log = logging.getLogger(__name__)


def _env_float(name: str, default: float, minimum: float) -> float:
    """Parse float from environment with minimum value constraint."""
    try:
        return max(minimum, float(os.getenv(name, default)))
    except ValueError:
        return default


def _env_chance(name: str, default: float) -> float:
    """Probability from environment, clamped to [0, 1]."""
    try:
        return min(1.0, max(0.0, float(os.getenv(name, default))))
    except ValueError:
        return default


def _env_int(name: str, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(os.getenv(name, default)))
    except ValueError:
        return default


CF_DEFAULT_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"


def _parse_names(raw: str) -> tuple[str, ...]:
    names = tuple(n.strip() for n in raw.split(",") if n.strip())
    return names or ("Бананыч",)


def _parse_ids(raw: str) -> frozenset[int]:
    """Parse comma or semicolon separated admin IDs."""
    ids: set[int] = set()
    for part in raw.replace(";", ",").replace(" ", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            raise RuntimeError(f"ADMIN_IDS: '{part}' is not a number") from None
    return frozenset(ids)


def _parse_chat_id(raw: str) -> int | None:
    """Parse group chat ID (can be None if empty)."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(f"GROUP_CHAT_ID: '{raw}' is not a number (expected format: -1001234567890)") from None


def _load_tz(name: str) -> tzinfo:
    """Load timezone or fallback to UTC."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        if name == "Europe/Moscow":
            log.warning("Europe/Moscow not found (Windows: run 'pip install tzdata') - using UTC+3")
            return timezone(timedelta(hours=3))
        log.warning("Unknown timezone '%s' (Windows: run 'pip install tzdata') - using UTC", name)
        return timezone.utc


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: frozenset[int]
    group_chat_id: int | None
    database_url: str
    tz: tzinfo
    shapt_cache_ttl: float
    shapt_poll_interval: float
    notifications_enabled: bool
    icons: dict[str, str]
    reactions_enabled: bool = True
    reaction_chance: float = 0.05
    # --- ИИ-собеседник ---
    ai_on: bool = True
    ai_api_key: str = ""
    ai_base_url: str = "https://api.groq.com/openai/v1"
    ai_model: str = "llama-3.3-70b-versatile"
    ai_cf_account_id: str = ""          # Cloudflare Workers AI: Account ID (если задан, base_url не нужен)
    ai_temperature: float = 0.8
    ai_names: tuple[str, ...] = ("Бананыч",)
    ai_random_chance: float = 0.04      # шанс влезть в случайное сообщение
    ai_followup_chance: float = 0.5     # шанс продолжить диалог с тем, кому только что ответил
    ai_cooldown: float = 25.0           # пауза между непрошеными ответами в чате, сек
    ai_max_per_hour: int = 40           # общий лимит ответов в час на чат
    ai_history_limit: int = 15          # сколько последних сообщений хранить и отдавать ИИ
    ai_history_ttl_hours: float = 6.0   # старше этого - удаляется
    ai_max_tokens: int = 200
    ai_mentions: bool = True            # может ли бот упоминать людей из недавнего лога

    @property
    def ai_enabled(self) -> bool:
        return self.ai_on and bool(self.ai_api_key)

    @property
    def tz_name(self) -> str:
        return getattr(self.tz, "key", None) or "UTC"

    def is_admin(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in self.admin_ids

    def is_group(self, chat_id: int | None) -> bool:
        return self.group_chat_id is not None and chat_id == self.group_chat_id


def load_config() -> Config:
    """Load configuration from environment."""
    poll_raw = os.getenv("SHAPT_POLL_INTERVAL", "600").strip()
    tz_name = os.getenv("TIMEZONE") or os.getenv("SCHEDULE_TZ") or "Europe/Moscow"
    cf_account = os.getenv("AI_CF_ACCOUNT_ID", "").strip()
    default_model = CF_DEFAULT_MODEL if cf_account else "llama-3.3-70b-versatile"
    return Config(
        bot_token=os.getenv("BOT_TOKEN", "").strip(),
        admin_ids=_parse_ids(os.getenv("ADMIN_IDS", "")),
        group_chat_id=_parse_chat_id(os.getenv("GROUP_CHAT_ID", "")),
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot.db").strip(),
        tz=_load_tz(tz_name),
        shapt_cache_ttl=_env_float("SHAPT_CACHE_TTL", 300, 30),
        shapt_poll_interval=_env_float("SHAPT_POLL_INTERVAL", 600, 60),
        notifications_enabled=poll_raw != "0",
        icons={
            "bells": os.getenv("ICON_BELLS", "5242628160297641831").strip(),
            "lessons": os.getenv("ICON_LESSONS", "5373098009640836781").strip(),
            "settings": os.getenv("ICON_SETTINGS", "5818705028424141605").strip(),
            "replacements": os.getenv("ICON_REPLACEMENTS", "5264727218734524899").strip(),
            "edit": os.getenv("ICON_EDIT", "5334673106202010226").strip(),
            "cancel": os.getenv("ICON_CANCEL", "5834629976883732083").strip(),
            "disable": os.getenv("ICON_DISABLE", "5244807637157029775").strip(),
            "panel": os.getenv("ICON_PANEL", "5449428597922079323").strip(),
            "calendar": os.getenv("ICON_CALENDAR", "5431897022456145283").strip(),
            "time": os.getenv("ICON_TIME", "5451732530048802485").strip(),
            "warning": os.getenv("ICON_WARNING", "5213181173026533794").strip(),
            "added": os.getenv("ICON_ADDED", "").strip(),
            "removed": os.getenv("ICON_REMOVED", "").strip(),
            "changed": os.getenv("ICON_CHANGED", "5334673106202010226").strip(),
        },
        reactions_enabled=os.getenv("REACTIONS_ENABLED", "1").strip() != "0",
        reaction_chance=_env_chance("REACTION_CHANCE", 0.05),
        ai_on=os.getenv("AI_ENABLED", "1").strip() != "0",
        ai_api_key=os.getenv("AI_API_KEY", "").strip(),
        ai_base_url=os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1").strip().rstrip("/"),
        ai_model=(os.getenv("AI_MODEL", "").strip() or default_model),
        ai_cf_account_id=cf_account,
        ai_temperature=_env_float("AI_TEMPERATURE", 0.8, 0),
        ai_names=_parse_names(os.getenv("AI_NAMES", "Бананыч")),
        ai_random_chance=_env_chance("AI_RANDOM_CHANCE", 0.04),
        ai_followup_chance=_env_chance("AI_FOLLOWUP_CHANCE", 0.5),
        ai_cooldown=_env_float("AI_COOLDOWN", 25, 0),
        ai_max_per_hour=_env_int("AI_MAX_PER_HOUR", 40, 1),
        ai_history_limit=_env_int("AI_HISTORY_LIMIT", 15, 2),
        ai_history_ttl_hours=_env_float("AI_HISTORY_TTL_HOURS", 6, 0.1),
        ai_max_tokens=_env_int("AI_MAX_TOKENS", 200, 32),
        ai_mentions=os.getenv("AI_MENTIONS", "1").strip() != "0",
    )


config = load_config()
