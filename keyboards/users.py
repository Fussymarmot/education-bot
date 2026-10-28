"""Keyboards for messages in the working group."""
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from config import config
from keyboards.callbacks import ReplCb, SchCb
from utils.schedule.schedule_logic import UPPER, LOWER


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Main menu keyboard shown on /start."""
    return None  # Placeholder - implement if needed


def week_kb(shown: str) -> InlineKeyboardMarkup:
    """Upper/lower week switcher."""
    b = InlineKeyboardBuilder()
    for label, value in (("⬆️ Верхняя", UPPER), ("⬇️ Нижняя", LOWER)):
        mark = "✅ " if shown == value else ""
        b.button(text=f"{mark}{label}", callback_data=SchCb(action="p", value=value))
    return b.adjust(2).as_markup()


def replacements_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Обновить", callback_data=ReplCb(action="refresh"), icon_custom_emoji_id=config.icons["replacements"])
    return b.as_markup()
