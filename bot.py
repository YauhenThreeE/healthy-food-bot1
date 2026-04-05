import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from dotenv import load_dotenv

from app.db.session import async_session_maker, init_db
from app.handlers.catalog import router as catalog_router
from app.handlers.onboarding import router as onboarding_router
from app.handlers.reminders import router as reminders_router
from app.handlers.tips import router as tips_router
from app.middlewares.db import DbSessionMiddleware
from app.services.dishes_seed import seed_dishes_if_empty
from app.services.reminders_runner import reminder_loop

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

if not BOT_TOKEN:
    raise ValueError(
        f"BOT_TOKEN not found in {ENV_PATH}. "
        "Create the file from .env.example and set your Telegram bot token."
    )

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

dp.update.middleware(DbSessionMiddleware())

dp.include_router(onboarding_router)
dp.include_router(catalog_router)
dp.include_router(reminders_router)
dp.include_router(tips_router)


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "👋 Привет!\n\n"
        "Я помогу тебе наладить полезное питание, подобрать блюда и вести рацион.\n\n"
        "Команды:\n"
        "/onboarding — профиль (цели, аллергии, бюджет…)\n"
        "/menu — меню блюд\n"
        "/tip — совет по питанию (нужен OPENAI_API_KEY)\n"
        "/remind и /reminders — напоминания\n"
        "/timezone — часовой пояс для напоминаний\n"
        "/help — все команды"
    )


@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "Доступные команды:\n"
        "/start — старт\n"
        "/onboarding — настройка профиля (сохраняется в БД)\n"
        "/menu — каталог блюд\n"
        "/tip [вопрос] — ИИ-совет с учётом профиля\n"
        "/remind ЧЧ:ММ текст — добавить напоминание\n"
        "/reminders — список и удаление\n"
        "/timezone Europe/Moscow — пояс для напоминаний\n"
        "/help — эта справка"
    )


async def main():
    await init_db()
    async with async_session_maker() as session:
        added = await seed_dishes_if_empty(session)
        if added:
            logging.getLogger(__name__).info("Seeded %s dishes", added)
        await session.commit()

    asyncio.create_task(reminder_loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
