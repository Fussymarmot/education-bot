"""Реакции: правила по ключевым словам, случайные реакции, валидность эмодзи."""
import inspect
import random
import re

from aiogram.types import ReactionTypeEmoji

from utils.common import reactions as r


def test_keyword_gives_reaction_from_its_rule():
    assert r.pick_reaction("Большое спасибо!", chance=0) in ("🙏", "🥰")
    assert r.pick_reaction("ПРИВЕТ всем", chance=0) in ("🤗", "🫡")
    assert r.pick_reaction("завтра зачёт", chance=0) in ("😱", "😨")
    assert r.pick_reaction("завтра зачет", chance=0) in ("😱", "😨")


def test_keyword_matches_only_at_word_start():
    assert r.match_keyword("кекс") is not None          # «кек…» в начале слова
    assert r.match_keyword("обработка") is None         # «бот» внутри слова не считается
    assert r.match_keyword("заменитель") is not None    # «замен…»


def test_no_keyword_no_chance_no_reaction():
    assert r.pick_reaction("обычное сообщение", chance=0) is None
    assert r.pick_reaction(None, chance=0) is None
    assert r.pick_reaction("", chance=0) is None


def test_random_reaction_respects_chance():
    assert r.pick_reaction("обычное сообщение", chance=1.0) in r.RANDOM_EMOJIS
    rng = random.Random(1)
    hits = sum(r.pick_reaction("обычное сообщение", chance=0.05, rng=rng) is not None for _ in range(10_000))
    assert 350 < hits < 650  # ~5%


def test_keyword_beats_random():
    # при chance=1 ключевое слово всё равно даёт реакцию по правилу, а не случайную
    assert r.pick_reaction("спасибо", chance=1.0, rng=random.Random(0)) in ("🙏", "🥰")


def test_all_emojis_are_allowed_by_telegram():
    # список разрешённых эмодзи лежит в докстринге поля emoji внутри исходника aiogram
    doc = inspect.getsource(ReactionTypeEmoji).split("it can be one of ", 1)[1].split(".\"\"\"", 1)[0]
    allowed = set(re.findall(r'"([^"]+)"', doc))
    assert len(allowed) > 50
    used = set(r.RANDOM_EMOJIS) | {e for rule in r.RULES for e in rule.emojis}
    bad = {e for e in used if e not in allowed}
    assert not bad, f"Эмодзи не разрешены для реакций ботов: {bad}"

