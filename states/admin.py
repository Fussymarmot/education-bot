"""FSM states of the administrator."""
from aiogram.fsm.state import State, StatesGroup


class Editor(StatesGroup):
    """Schedule editor: the bot waits for text from the administrator."""

    bells = State()   # full bell list of one shift
    day = State()     # schedule of one day
    repl_group = State()   # group name for replacements
