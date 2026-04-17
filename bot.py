import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from dotenv import load_dotenv

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import User
from app.db.session import async_session_maker, init_db
from app.handlers.catalog import router as catalog_router
from app.handlers.food_log import router as food_log_router
from app.handlers.navigation import router as navigation_router
from app.handlers.onboarding import router as onboarding_router
from app.handlers.orders import router as orders_router
from app.handlers.profile import router as profile_router
from app.handlers.reminders import router as reminders_router
from app.handlers.tips import router as tips_router
from app.keyboards.start import after_start_keyboard
from app.middlewares.db import DbSessionMiddleware
from app.services.dishes_seed import seed_dishes_if_empty
from app.services.reminders_runner import reminder_loop
from app.services.products_seed import seed_products_if_empty
from app.services.user_profile import ensure_telegram_user

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

dp.include_router(profile_router)
dp.include_router(tips_router)
dp.include_router(food_log_router)
dp.include_router(orders_router)
dp.include_router(onboarding_router)
dp.include_router(catalog_router)
dp.include_router(reminders_router)
dp.include_router(navigation_router)


@dp.message(CommandStart())
async def start_handler(message: Message, session: AsyncSession):
    u = message.from_user
    await ensure_telegram_user(session, u.id, u.username, u.first_name)

    result = await session.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.telegram_id == u.id)
    )
    user = result.scalar_one_or_none()
    has_profile = user and user.profile and user.profile.goal

    if has_profile:
        await message.answer(
            f"👋 С возвращением, {u.first_name or 'друг'}!\n\n"
            "Твой профиль уже заполнен. Что хочешь сделать?",
            reply_markup=after_start_keyboard(),
        )
    else:
        await message.answer(
            f"👋 Привет, {u.first_name or 'друг'}!\n\n"
            "Я помогу тебе наладить полезное питание, подобрать блюда и вести рацион.\n\n"
            "Для начала давай настроим твой профиль — это займёт пару минут.\n"
            "Нажми кнопку ниже 👇",
            reply_markup=after_start_keyboard(show_profile=False),
        )


@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "Доступные команды:\n\n"
        "👤 Профиль\n"
        "/onboarding — настройка профиля\n"
        "/profile — посмотреть свой профиль\n\n"
        "🍽 Еда\n"
        "/menu — каталог блюд\n"
        "/order — оформить заказ\n\n"
        "🤖 ИИ-советы\n"
        "/tip [вопрос] — совет по питанию\n\n"
        "📊 Трекинг питания\n"
        "/log_food продукт 200 г — добавить еду\n"
        "/log_meal ... — alias для логирования\n"
        "/today — дневной итог\n"
        "/advice — рекомендации по рациону\n"
        "/parse_meal текст — распознать свободный ввод\n"
        "/remember key=value — сохранить факт в AI памяти\n\n"
        "⏰ Напоминания\n"
        "/remind ЧЧ:ММ текст — добавить\n"
        "/reminders — список и удаление\n"
        "/timezone — часовой пояс\n\n"
        "/help — эта справка"
    )


async def main():
    await init_db()
    async with async_session_maker() as session:
        added = await seed_dishes_if_empty(session)
        if added:
            logging.getLogger(__name__).info("Seeded %s dishes", added)
        products_added = await seed_products_if_empty(session)
        if products_added:
            logging.getLogger(__name__).info("Seeded %s products", products_added)
        await session.commit()

    asyncio.create_task(reminder_loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
