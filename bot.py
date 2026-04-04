import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from dotenv import load_dotenv

from app.handlers.onboarding import router as onboarding_router

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

dp.include_router(onboarding_router)


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "👋 Привет!\n\n"
        "Я помогу тебе наладить полезное питание, подобрать блюда и вести рацион.\n\n"
        "Нажми /onboarding чтобы заполнить профиль."
    )


@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "Доступные команды:\n"
        "/start — старт\n"
        "/onboarding — настройка профиля\n"
        "/help — помощь"
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
