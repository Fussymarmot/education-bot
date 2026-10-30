"""ИИ-собеседник: решение отвечать, чистка ответа, память в БД."""
import asyncio
import random

from database import close_db, init_db
from database.ai_queries import add_message, clear_chat, get_context
from utils.ai.persona import build_messages, clean_reply, name_pattern
from utils.ai.policy import Gate


class Clock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t


def gate(**kw):
    base = dict(random_chance=0.0, followup_chance=0.0, cooldown=25, max_per_hour=3)
    base.update(kw)
    clock = Clock()
    return Gate(**base, clock=clock, rng=random.Random(1)), clock


def test_direct_always_replies_and_is_forced():
    g, _ = gate()
    d = g.decide(1, 10, "ок", direct=True)
    assert d.reply and d.forced


def test_plain_message_ignored_without_luck():
    g, _ = gate()
    assert not g.decide(1, 10, "обычное сообщение про погоду", direct=False).reply


def test_topic_does_not_change_random_reply_probability():
    g, _ = gate(random_chance=1.0)
    for text in ("завтра на пару не приду", "обсудим технологии", "что посмотреть вечером", "как дела"):
        decision = g.decide(hash(text), 10, text, direct=False)
        assert decision.reply and decision.reason == "random"


def test_cooldown_and_hour_limit():
    g, clock = gate()
    g.mark_replied(1, 10)
    assert not g.decide(1, 11, "я опоздаю на пару", direct=False).reply      # кулдаун
    assert g.decide(1, 11, "бот, ты где", direct=True).reply                 # прямое обращение мимо кулдауна
    clock.t += 30
    assert g.decide(1, 11, "я опоздаю на пару", direct=False).reply
    g.mark_replied(1, 10); g.mark_replied(1, 10)                             # 3 ответа = лимит
    assert not g.decide(1, 10, "бот", direct=True).reply
    clock.t += 3601
    assert g.decide(1, 10, "бот", direct=True).reply


def test_followup_only_for_same_user():
    g, clock = gate(followup_chance=1.0)
    g.mark_replied(1, 10)
    clock.t += 30
    assert g.decide(1, 10, "сам ты такой", direct=False).reason == "followup"
    assert not g.decide(1, 99, "сам ты такой", direct=False).reply


def test_name_pattern():
    p = name_pattern(("Бананыч",))
    assert p.search("эй, бананыч, ты тут?") and p.search("Бананыча позовите")
    assert not p.search("банан")


def test_clean_reply():
    assert clean_reply("SKIP", "Бананыч") is None
    assert clean_reply(" skip. ", "Бананыч") is None
    assert clean_reply("", "Бананыч") is None
    assert clean_reply("Бананыч: иди на пару", "Бананыч") == "иди на пару"
    assert clean_reply("<think>хм</think>«Лентяй»", "Бананыч") == "Лентяй"


def test_memory_is_pruned_and_ordered():
    async def run():
        await init_db()
        await clear_chat(7)
        for i in range(10):
            await add_message(7, 1, "user", "Вася", f"msg{i}", keep=4, ttl_hours=6, now=5000.0 + i)
        ctx = await get_context(7, 15)
        assert [l.content for l in ctx] == ["msg6", "msg7", "msg8", "msg9"]
        # старые по TTL уходят при следующей записи
        await add_message(7, None, "assistant", "Бананыч", "ответ", keep=4, ttl_hours=6, now=5000.0 + 7 * 3600)
        ctx = await get_context(7, 15)
        assert [l.content for l in ctx] == ["ответ"]
        msgs = build_messages("Бананыч", ctx, forced=True)
        assert msgs[0]["role"] == "system" and "Бананыч: ответ" in msgs[1]["content"]
        await close_db()
    asyncio.run(run())


def test_mentions_only_known_unique_names():
    from database.ai_queries import Line
    from utils.ai.mentions import participants, render_mentions
    hist = [Line("user", "Вася", "привет", 1), Line("user", "Маша", "хай", 2),
            Line("user", "Иван", "а", 3), Line("user", "Иван", "б", 4), Line("assistant", "Бананыч", "ну", None)]
    people = participants(hist)
    assert people == {"Вася": 1, "Маша": 2}                      # дубль «Иван» и бот отсечены
    out = render_mentions("Вася, ты опять <b>не пришёл</b>? Иван молчит, Васю не спрашиваю", people)
    assert out.count('<a href="tg://user?id=1">Вася</a>') == 1   # упоминаем один раз, только точное имя
    assert "&lt;b&gt;" in out and "tg://user?id=2" not in out    # HTML экранирован, Маши в тексте нет
    assert render_mentions("Привет, Вася.", {"Вася": 1}) == 'Привет, <a href="tg://user?id=1">Вася</a>.'
    assert render_mentions("Привет", {}) == "Привет"


def test_creator_marked_in_log_by_id():
    from database.ai_queries import Line
    msgs = build_messages("Бананыч", [Line("user", "Админ", "я тут", 111), Line("user", "Вася", "и я", 1)],
                          forced=True, creator_ids=frozenset({111}), people={"Админ": 111, "Вася": 1})
    text = msgs[1]["content"]
    assert "Админ (создатель): я тут" in text and "Вася: и я" in text and "Участники чата: Админ, Вася." in text
