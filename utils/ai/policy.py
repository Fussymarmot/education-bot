"""Решает, отвечать ли на сообщение. Без обращений к ИИ - дёшево и без лишних токенов."""
from __future__ import annotations

import random
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

from utils.common.reactions import ABSENCE_RE

DIALOG_WINDOW = 120.0   # сек: после ответа человеку считаем, что диалог с ним ещё идёт
MIN_LEN = 4             # совсем короткое («ок», «+») игнорируем, если не звали


@dataclass(frozen=True)
class Decision:
    reply: bool
    forced: bool = False   # True: обратились напрямую, молчать (SKIP) нельзя
    reason: str = ""


class Gate:
    def __init__(self, *, random_chance: float, absence_chance: float, followup_chance: float,
                 cooldown: float, max_per_hour: int,
                 clock: Callable[[], float] = time.monotonic, rng: random.Random | None = None) -> None:
        self.random_chance = random_chance
        self.absence_chance = absence_chance
        self.followup_chance = followup_chance
        self.cooldown = cooldown
        self.max_per_hour = max_per_hour
        self._clock = clock
        self._rng = rng or random.Random()
        self._last_any: dict[int, float] = {}
        self._last_to_user: dict[tuple[int, int], float] = {}
        self._hour: dict[int, deque[float]] = {}

    def _hour_full(self, chat_id: int, now: float) -> bool:
        q = self._hour.setdefault(chat_id, deque())
        while q and now - q[0] > 3600:
            q.popleft()
        return len(q) >= self.max_per_hour

    def decide(self, chat_id: int, user_id: int | None, text: str, *, direct: bool) -> Decision:
        now = self._clock()
        if self._hour_full(chat_id, now):
            return Decision(False, reason="hour-limit")
        if direct:
            return Decision(True, forced=True, reason="direct")
        if len(text.strip()) < MIN_LEN:
            return Decision(False, reason="short")
        if now - self._last_any.get(chat_id, -1e9) < self.cooldown:
            return Decision(False, reason="cooldown")
        if ABSENCE_RE.search(text) and self._rng.random() < self.absence_chance:
            return Decision(True, forced=True, reason="absence")
        in_dialog = now - self._last_to_user.get((chat_id, user_id or 0), -1e9) < DIALOG_WINDOW
        if in_dialog and self._rng.random() < self.followup_chance:
            return Decision(True, reason="followup")
        if self._rng.random() < self.random_chance:
            return Decision(True, reason="random")
        return Decision(False, reason="no-luck")

    def mark_replied(self, chat_id: int, user_id: int | None) -> None:
        now = self._clock()
        self._last_any[chat_id] = now
        self._last_to_user[(chat_id, user_id or 0)] = now
        self._hour.setdefault(chat_id, deque()).append(now)
