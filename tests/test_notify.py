"""Replacement change notifications: work group only, and only for the group chosen by the administrator."""
import asyncio
from dataclasses import replace
from datetime import date

import pytest

from database import close_db, init_db, queries
from utils.replacements import replacements_logic as rl
from utils import replacements_service as svc

TODAY = date(2026, 10, 15)


def rep(group, lesson="1"):
    return rl.Replacement(TODAY, "I смена", rl.normalize_cells([group, lesson, "Математика", "301", "Иванова"]))


@pytest.fixture
def run():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(init_db())
    yield loop.run_until_complete
    loop.run_until_complete(close_db())
    loop.close()


@pytest.fixture
def sent(monkeypatch):
    out = []

    async def fake_send(bot, chat_id, chunks, **extra):
        out.append((chat_id, "\n".join(chunks)))

    monkeypatch.setattr(svc, "send_html", fake_send)
    return out


def changes(*items):
    return rl.diff_items([], list(items))


def test_sends_only_selected_group_to_work_chat(run, sent):
    run(queries.set_replacements_group("ИС-21"))
    run(svc._notify(None, changes(rep("ИС-21"), rep("ИС-22", "2"))))
    assert len(sent) == 1 and sent[0][0] == -1001
    assert "ИС-21" in sent[0][1] and "ИС-22" not in sent[0][1]


def test_nothing_sent_when_group_not_selected(run, sent):
    run(queries.set_replacements_group(None))
    run(svc._notify(None, changes(rep("ИС-21"))))
    assert sent == []


def test_nothing_sent_when_no_changes_for_selected_group(run, sent):
    run(queries.set_replacements_group("ПО-11"))
    run(svc._notify(None, changes(rep("ИС-21"))))
    assert sent == []


def test_nothing_sent_without_work_chat(run, sent, monkeypatch):
    run(queries.set_replacements_group("ИС-21"))
    monkeypatch.setattr(svc, "config", replace(svc.config, group_chat_id=None))
    run(svc._notify(None, changes(rep("ИС-21"))))
    assert sent == []
