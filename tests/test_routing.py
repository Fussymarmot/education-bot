"""Who gets an answer from the bot and where: aiogram dispatcher + a fake Telegram session (no network)."""
import asyncio
from datetime import datetime

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from database import close_db, init_db, queries
from handlers import setup_routers
from keyboards.callbacks import EdCb

ADMIN, USER, GROUP = 111, 222, -1001


class FakeSession(BaseSession):
    """Records outgoing requests instead of calling Telegram."""

    def __init__(self):
        super().__init__()
        self.calls: list[tuple[str, dict]] = []

    async def close(self):
        pass

    async def stream_content(self, *a, **kw):  # pragma: no cover
        raise NotImplementedError

    async def make_request(self, bot, method: TelegramMethod, timeout=None):
        data = method.model_dump(exclude_none=True)
        self.calls.append((method.__api_method__, data))
        returns = getattr(method, "__returns__", None)
        if returns is Message or "Message" in str(returns):
            chat = Chat(id=data.get("chat_id", 0), type="private")
            return Message(message_id=len(self.calls), date=datetime.now(), chat=chat)
        return True


def _message(chat_id: int, user_id: int, text: str, chat_type: str) -> Update:
    entities = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}] if text.startswith("/") else None
    return Update.model_validate({
        "update_id": 1,
        "message": {
            "message_id": 10, "date": int(datetime.now().timestamp()),
            "chat": {"id": chat_id, "type": chat_type},
            "from": {"id": user_id, "is_bot": False, "first_name": "T"},
            "text": text, **({"entities": entities} if entities else {}),
        },
    })


def _callback(chat_id: int, user_id: int, data: str, chat_type: str) -> Update:
    return Update.model_validate({
        "update_id": 2,
        "callback_query": {
            "id": "1", "chat_instance": "x", "data": data,
            "from": {"id": user_id, "is_bot": False, "first_name": "T"},
            "message": {"message_id": 10, "date": int(datetime.now().timestamp()),
                        "chat": {"id": chat_id, "type": chat_type, "first_name": "T"},
                        "from": {"id": 1, "is_bot": True, "first_name": "bot"}, "text": "панель"},
        },
    })


@pytest.fixture(scope="module")
def env():   # routers are bound to the dispatcher once, so it is one per module
    async def build():
        await init_db()
        session = FakeSession()
        bot = Bot("123456:TEST", session=session)
        dp = Dispatcher(storage=MemoryStorage())
        dp.include_router(setup_routers())
        return bot, dp, session

    loop = asyncio.new_event_loop()
    bot, dp, session = loop.run_until_complete(build())

    def feed(update: Update):
        session.calls.clear()
        loop.run_until_complete(dp.feed_update(bot, update))
        return [name for name, _ in session.calls]

    feed.session = session
    feed.run = loop.run_until_complete
    yield feed
    loop.run_until_complete(close_db())
    loop.close()


def test_admin_start_opens_editor(env):
    assert env(_message(ADMIN, ADMIN, "/start", "private")) == ["sendMessage"]
    text = env.session.calls[0][1]["text"]
    assert "Редактор расписания" in text and "Замены в группе" in text


def test_non_admin_private_gets_no_answer(env):
    for text in ("/start", "/bells", "/schedule", "/replacements", "/schedule_edit", "привет"):
        assert env(_message(USER, USER, text, "private")) == [], text


def test_editing_commands_are_gone_for_admin(env):
    for text in ("/schedule_edit", "/replacements_sub ИС-21", "/replacements_unsub"):
        assert env(_message(ADMIN, ADMIN, text, "private")) == [], text


def test_admin_in_private_does_not_get_public_commands(env):
    assert env(_message(ADMIN, ADMIN, "/bells", "private")) == []


def test_non_admin_cannot_press_editor_buttons(env):
    assert env(_callback(USER, USER, EdCb(action="menu").pack(), "private")) == []


def test_group_commands_work_for_everyone(env):
    assert env(_message(GROUP, USER, "/bells", "supergroup"))
    for command in ("/today", "/week", "/schedule"):
        assert env(_message(GROUP, USER, command, "supergroup")), command
    assert env(_message(GROUP, USER, "/help", "supergroup")) == ["sendMessage"]


def test_editor_is_not_reachable_from_group(env):
    assert env(_message(GROUP, ADMIN, "/start", "supergroup")) == []
    assert env(_callback(GROUP, ADMIN, EdCb(action="menu").pack(), "supergroup")) == []
    assert env(_callback(GROUP, ADMIN, EdCb(action="repl").pack(), "supergroup")) == []


def test_other_groups_are_ignored(env):
    for text in ("/bells", "/today", "/week", "/schedule", "/replacements", "/help", "/start"):
        assert env(_message(-999, ADMIN, text, "supergroup")) == [], text
    assert env(_callback(-999, USER, "sch:p:upper", "supergroup")) == []


def test_replacements_command_shows_all_groups(env, monkeypatch):
    """On command - replacements of all groups, even if the admin chose a group for automatic notifications."""
    from handlers import users
    seen = []

    async def fake_build(group, *, force=False):
        seen.append(group)
        raise RuntimeError("no network")   # the handler then answers with an error message

    monkeypatch.setattr(users.repl, "build", fake_build)
    env.run(queries.set_replacements_group("ИС-21"))
    env(_message(GROUP, USER, "/replacements", "supergroup"))
    assert seen == [None]


def test_admin_sets_and_clears_replacements_group(env):
    env.run(queries.set_replacements_group(None))
    assert env(_callback(ADMIN, ADMIN, EdCb(action="redit").pack(), "private")) == ["answerCallbackQuery", "editMessageText"]
    env(_message(ADMIN, ADMIN, "  ИС-21 ", "private"))
    assert env.run(queries.get_replacements_group()) == "ИС-21"
    env(_callback(ADMIN, ADMIN, EdCb(action="rclear").pack(), "private"))
    assert env.run(queries.get_replacements_group()) is None


def test_too_long_group_name_is_rejected(env):
    env.run(queries.set_replacements_group("ПО-11"))
    env(_callback(ADMIN, ADMIN, EdCb(action="redit").pack(), "private"))
    env(_message(ADMIN, ADMIN, "х" * 40, "private"))
    assert env.run(queries.get_replacements_group()) == "ПО-11"   # unchanged


def test_group_name_from_non_admin_is_ignored(env):
    env.run(queries.set_replacements_group("ПО-11"))
    env(_message(USER, USER, "ИС-21", "private"))
    assert env.run(queries.get_replacements_group()) == "ПО-11"


def test_every_editor_button_is_handled(env):
    from keyboards import admin as kbs

    markups = [
        kbs.menu_kb(), kbs.bells_menu_kb({0, 5}), kbs.days_kb({d: d for d in range(7)}),
        kbs.settings_kb(1), kbs.repl_kb(True), kbs.repl_kb(False), kbs.repl_prompt_kb(),
        *[kbs.bscope_kb(d, 3, 4) for d in range(-1, 7)],
        *[kbs.bshift_kb(d, s, h) for d in range(-1, 7) for s in (1, 2) for h in (True, False)],
        *[kbs.bells_prompt_kb(d, 1) for d in (-1, 6)],
        *[kbs.bclear_confirm_kb(d, s) for d in (-1, 3) for s in (1, 2)],
        *[kbs.day_kb(d, h) for d in range(7) for h in (True, False)],
        *[kbs.day_prompt_kb(d) for d in range(7)], *[kbs.dclear_confirm_kb(d) for d in range(7)],
    ]
    unhandled = []
    for markup in markups:
        for row in markup.inline_keyboard:
            for button in row:
                EdCb.unpack(button.callback_data)   # the format is valid and fits into 64 bytes
                assert len(button.callback_data.encode()) <= 64
                if not env(_callback(ADMIN, ADMIN, button.callback_data, "private")):
                    unhandled.append((button.text, button.callback_data))
    assert not unhandled


# --- интеграция: настоящий диспетчер + фейковая сессия Telegram -----------------
from dataclasses import replace  # noqa: E402

from config import config  # noqa: E402
from utils.common import reactions as r  # noqa: E402


def _no_random(monkeypatch, chance=0.0, enabled=True):
    from handlers import reactions as handler
    monkeypatch.setattr(handler, "config", replace(config, reaction_chance=chance, reactions_enabled=enabled))


def test_keyword_in_group_sets_reaction(env, monkeypatch):
    _no_random(monkeypatch)
    assert env(_message(GROUP, USER, "всем привет!", "supergroup")) == ["setMessageReaction"]
    data = env.session.calls[0][1]
    assert data["chat_id"] == GROUP and data["message_id"] == 10
    assert data["reaction"][0]["emoji"] in ("🤗", "🫡")


def test_plain_message_without_chance_gets_nothing(env, monkeypatch):
    _no_random(monkeypatch, chance=0.0)
    assert env(_message(GROUP, USER, "какое-то обычное сообщение", "supergroup")) == []


def test_plain_message_with_full_chance_gets_random_emoji(env, monkeypatch):
    _no_random(monkeypatch, chance=1.0)
    assert env(_message(GROUP, USER, "какое-то обычное сообщение", "supergroup")) == ["setMessageReaction"]
    assert env.session.calls[0][1]["reaction"][0]["emoji"] in r.RANDOM_EMOJIS


def test_commands_still_answer_and_are_not_reacted(env, monkeypatch):
    _no_random(monkeypatch, chance=1.0)
    names = env(_message(GROUP, USER, "/help", "supergroup"))
    assert names == ["sendMessage"]


def test_other_chats_get_no_reactions(env, monkeypatch):
    _no_random(monkeypatch, chance=1.0)
    assert env(_message(-999, USER, "спасибо", "supergroup")) == []
    assert env(_message(USER, USER, "спасибо", "private")) == []


def test_reactions_can_be_disabled(env, monkeypatch):
    _no_random(monkeypatch, chance=1.0, enabled=False)
    assert env(_message(GROUP, USER, "спасибо", "supergroup")) == []
