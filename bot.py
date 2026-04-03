import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "👋 Welcome!\n\n"
        "I help you eat healthy, plan meals and order food kits.\n\n"
        "Use /menu to see meals\n"
        "Use /journal to log food"
    )


@dp.message()
async def echo(message: Message):
    await message.answer("Got it. I'll analyze your nutrition later 😉")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
