"""Callback data and button identifiers."""
from aiogram.filters.callback_data import CallbackData

class SchCb(CallbackData, prefix="sch"):
    """Weekly schedule buttons."""
    action: str
    value: str = ""


class EdCb(CallbackData, prefix="sce"):
    """Schedule editor buttons (admin). day: -1=regular, 0..6=Mon..Sun."""
    action: str
    day: int = 0
    shift: int = 0
    week: str = ""


class ReplCb(CallbackData, prefix="shr"):
    action: str
    group: str = ""
