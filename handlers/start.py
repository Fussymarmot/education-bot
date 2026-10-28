"""/start and /help."""
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from config import config
from keyboards.users import main_menu
from utils.common.commands import PUBLIC, admin_commands

router = Router(name="start")


@router.message(CommandStart())
async def start(message: Message) -> None:
    is_admin = config.is_admin(message.from_user.id if message.from_user else None)
    await message.answer("Привет! Выберите, что показать:", reply_markup=main_menu(is_admin))


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    is_admin = config.is_admin(message.from_user.id if message.from_user else None)
    commands = PUBLIC + (admin_commands() if is_admin else [])
    await message.answer("\n".join(f"/{name} — {description}" for name, description in commands))
