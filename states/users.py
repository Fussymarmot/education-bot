"""FSM states of regular users.

Public commands (/bells, /schedule, /replacements) have no text-input scenarios yet,
so the group is empty. Add new scenarios here.
"""
from aiogram.fsm.state import StatesGroup


class Users(StatesGroup):
    pass
