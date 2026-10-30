"""Реакции: правила по ключевым словам, случайные реакции, валидность эмодзи."""
import inspect
import random
import re

from aiogram.types import ReactionTypeEmoji

from utils.common import reactions as r


def test_keyword_gives_reaction_from_its_rule():
    assert r.pick_reaction("Большое спасибо!", chance=0) in ("🙏", "🥰", "🤝", "💋")
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
    assert r.pick_reaction("спасибо", chance=1.0, rng=random.Random(0)) in ("🙏", "🥰", "🤝", "💋")


def test_all_emojis_are_allowed_by_telegram():
    # список разрешённых эмодзи лежит в докстринге поля emoji внутри исходника aiogram
    doc = inspect.getsource(ReactionTypeEmoji).split("it can be one of ", 1)[1].split(".\"\"\"", 1)[0]
    allowed = set(re.findall(r'"([^"]+)"', doc))
    assert len(allowed) > 50
    used = set(r.RANDOM_EMOJIS) | {e for rule in r.RULES for e in rule.emojis}
    bad = {e for e in used if e not in allowed}
    assert not bad, f"Эмодзи не разрешены для реакций ботов: {bad}"



ANGRY = ("🤬", "💩", "🤮", "😡", "🖕")


def test_absence_phrases_get_angry_reaction():
    phrases = [
        "я не приду", "Завтра я не приду", "не придёшь?", "он не придет", "они не придут",
        "мы не придём", "вы не придёте?", "не пойду на пару", "не пойдём", "я не поеду",
        "не приеду сегодня", "не смогу прийти", "не можем быть", "завтра не получится прийти",
        "не явлюсь", "он не пришёл", "она не пришла", "меня не будет", "нас не будет завтра",
        "я не буду", "не будет его", "отсутствую", "опоздаю на пару", "опоздаете", "пропущу",
        "прогуляю физру", "не успею на пару",
        "не приду на зачёт",       # раньше перехватывалось правилом «зачёт»
        "Привет, меня не будет",   # раньше перехватывалось приветствием
    ]
    for text in phrases:
        assert r.match_keyword(text) in ANGRY, text


def test_absence_does_not_trigger_on_lookalikes():
    for text in ["не придумал", "это не является проблемой", "не пришло в голову",
                 "не смогу решить задачу", "не пойдите"]:
        assert r.match_keyword(text) not in ANGRY, text


def test_no_classes_still_means_holiday():
    assert r.match_keyword("завтра пар не будет") in ("🎉", "😍")
    assert r.match_keyword("пары не будет") in ("🎉", "😍")


def test_greetings_all_forms():
    for text in ["привет", "Всем привет!", "всем приветик", "приветт", "прив", "всем првиет", "здарова",
                 "дарова всем", "хэй", "hello", "Hi all", "салам", "ку", "доброго времени суток",
                 "доброй ночи", "здравствуйте", "добрый вечер"]:
        assert r.match_keyword(text) in ("🤗", "🫡"), text
    for text in ["куртка", "history", "высшее", "приведу пример"]:
        assert r.match_keyword(text) not in ("🤗", "🫡"), text


def test_class_cancelled_is_happy_in_any_word_order():
    for text in ["завтра первой пары не будет", "Завтра первой пары не будет!", "первых двух пар не будет",
                 "пары не будет", "не будет пары", "завтра не будет первой пары", "пары завтра не будет",
                 "занятий не будет", "лекции не будет", "физры не будет", "препода не будет",
                 "препода сегодня не будет", "урока не будет", "не будет физкультуры"]:
        assert r.match_keyword(text) in ("🎉", "😍"), text


def test_person_absent_from_class_is_still_angry():
    for text in ["меня завтра не будет на паре", "на лекции меня не будет", "на паре меня не будет",
                 "я на паре не буду", "завтра не буду на лекции", "не будет меня на паре",
                 "нас не будет на лекции", "не приду на пару", "Иванова не будет"]:
        assert r.match_keyword(text) in ANGRY, text
