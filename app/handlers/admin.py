from __future__ import annotations

import os
from datetime import date, timedelta

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Conversation, DailySummary, MealLog, Product, User

router = Router()


def _admin_id() -> int | None:
    raw = (os.getenv("ADMIN_TELEGRAM_ID") or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _is_admin(message: Message) -> bool:
    admin_id = _admin_id()
    return bool(admin_id and message.from_user and message.from_user.id == admin_id)


async def _reject_non_admin(message: Message) -> bool:
    if _is_admin(message):
        return False
    await message.answer("Команда доступна только администратору.")
    return True


def _fmt_dt(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else "-"


def _display_user(user: User) -> str:
    username = f"@{user.username}" if user.username else "без username"
    name = " ".join(part for part in [user.first_name, user.last_name] if part) or "без имени"
    return f"{name} ({username}), id={user.telegram_id}"


@router.message(Command("admin_report"))
async def cmd_admin_report(message: Message, session: AsyncSession):
    if await _reject_non_admin(message):
        return

    today = date.today()
    week_ago = today - timedelta(days=7)
    total_users = await session.scalar(select(func.count()).select_from(User)) or 0
    users_with_profile = (
        await session.scalar(select(func.count()).select_from(User).where(User.goal.is_not(None), User.goal != ""))
        or 0
    )
    meals_today = (
        await session.scalar(select(func.count()).select_from(MealLog).where(MealLog.date == today))
        or 0
    )
    meals_week = (
        await session.scalar(select(func.count()).select_from(MealLog).where(MealLog.date >= week_ago))
        or 0
    )
    food_days_total = (
        await session.scalar(select(func.count(func.distinct(MealLog.date))).select_from(MealLog))
        or 0
    )
    ai_products = (
        await session.scalar(select(func.count()).select_from(Product).where(Product.is_verified.is_(False)))
        or 0
    )
    conversations_week = (
        await session.scalar(
            select(func.count()).select_from(Conversation).where(func.date(Conversation.created_at) >= week_ago)
        )
        or 0
    )

    await message.answer(
        "Админ-отчёт:\n"
        f"Пользователей всего: {total_users}\n"
        f"С заполненной целью: {users_with_profile}\n"
        f"Записей еды сегодня: {meals_today}\n"
        f"Записей еды за 7 дней: {meals_week}\n"
        f"Дней с записями еды: {food_days_total}\n"
        f"AI-продуктов в базе: {ai_products}\n"
        f"Сообщений/событий за 7 дней: {conversations_week}\n\n"
        "Команды:\n"
        "/admin_users\n"
        "/admin_user <telegram_id>\n"
        "/admin_food <telegram_id> [days]"
    )


@router.message(Command("admin_users"))
async def cmd_admin_users(message: Message, session: AsyncSession):
    if await _reject_non_admin(message):
        return

    result = await session.execute(
        select(User)
        .options(selectinload(User.profile))
        .order_by(User.created_at.desc())
        .limit(20)
    )
    users = list(result.scalars())
    if not users:
        await message.answer("Пользователей пока нет.")
        return

    lines = ["Последние пользователи:"]
    for user in users:
        meal_count = (
            await session.scalar(select(func.count()).select_from(MealLog).where(MealLog.user_id == user.id))
            or 0
        )
        food_days = (
            await session.scalar(
                select(func.count(func.distinct(MealLog.date)))
                .select_from(MealLog)
                .where(MealLog.user_id == user.id)
            )
            or 0
        )
        lines.append(
            f"• {_display_user(user)}\n"
            f"  создан: {_fmt_dt(user.created_at)}, цель: {user.goal or '-'}, "
            f"еда: {meal_count}, дней: {food_days}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("admin_user"))
async def cmd_admin_user(message: Message, command: CommandObject, session: AsyncSession):
    if await _reject_non_admin(message):
        return

    raw_id = (command.args or "").strip()
    if not raw_id.isdigit():
        await message.answer("Формат: /admin_user <telegram_id>")
        return

    result = await session.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.telegram_id == int(raw_id))
    )
    user = result.scalar_one_or_none()
    if not user:
        await message.answer("Пользователь не найден.")
        return

    meal_count = await session.scalar(select(func.count()).select_from(MealLog).where(MealLog.user_id == user.id)) or 0
    food_days = (
        await session.scalar(
            select(func.count(func.distinct(MealLog.date)))
            .select_from(MealLog)
            .where(MealLog.user_id == user.id)
        )
        or 0
    )
    first_food_day = (
        await session.scalar(select(func.min(MealLog.date)).where(MealLog.user_id == user.id))
    )
    last_food_day = (
        await session.scalar(select(func.max(MealLog.date)).where(MealLog.user_id == user.id))
    )
    last_meal = (
        await session.execute(
            select(MealLog)
            .where(MealLog.user_id == user.id)
            .order_by(MealLog.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    last_conversation = (
        await session.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    await message.answer(
        "Пользователь:\n"
        f"{_display_user(user)}\n"
        f"Создан: {_fmt_dt(user.created_at)}\n"
        f"Обновлён: {_fmt_dt(user.updated_at)}\n"
        f"Цель: {user.goal or '-'}\n"
        f"Пол/возраст: {user.sex or '-'} / {user.age or '-'}\n"
        f"Рост/вес: {user.height_cm or '-'} см / {user.weight_kg or '-'} кг\n"
        f"Тип питания: {user.diet_type or '-'}\n"
        f"Цель ккал: {user.daily_calories_target or '-'}\n"
        f"Записей еды: {meal_count}\n"
        f"Дней записывал еду: {food_days}\n"
        f"Период еды: {first_food_day or '-'} — {last_food_day or '-'}\n"
        f"Последняя еда: {(last_meal.custom_name if last_meal else '-')}\n"
        f"Последнее событие: {(last_conversation.intent if last_conversation else '-')}"
    )


@router.message(Command("admin_food"))
async def cmd_admin_food(message: Message, command: CommandObject, session: AsyncSession):
    if await _reject_non_admin(message):
        return

    args = (command.args or "").split()
    raw_id = args[0] if args else ""
    if not raw_id.isdigit():
        await message.answer("Формат: /admin_food <telegram_id> [days]\nПример: /admin_food 123456789 7")
        return
    days = 7
    if len(args) > 1 and args[1].isdigit():
        days = min(max(int(args[1]), 1), 60)

    user = (
        await session.execute(select(User).where(User.telegram_id == int(raw_id)))
    ).scalar_one_or_none()
    if not user:
        await message.answer("Пользователь не найден.")
        return

    since = date.today() - timedelta(days=days - 1)
    logs = list(
        (
            await session.execute(
                select(MealLog)
                .where(MealLog.user_id == user.id, MealLog.date >= since)
                .order_by(MealLog.created_at.desc())
                .limit(60)
            )
        ).scalars()
    )
    if not logs:
        await message.answer("У пользователя пока нет записей еды.")
        return

    summary = (
        await session.execute(
            select(DailySummary)
            .where(DailySummary.user_id == user.id)
            .order_by(DailySummary.date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    food_days = (
        await session.scalar(
            select(func.count(func.distinct(MealLog.date)))
            .select_from(MealLog)
            .where(MealLog.user_id == user.id)
        )
        or 0
    )
    lines = [f"Питание: {_display_user(user)}"]
    lines.append(f"Всего дней с едой: {food_days}; показан период: {days} дн.")
    if summary:
        lines.append(
            f"Последний итог {summary.date}: "
            f"{summary.calories_fact:.0f}/{summary.calories_target:.0f} ккал"
        )
    lines.append("Последние записи:")
    for row in logs:
        lines.append(
            f"• {row.date} {row.custom_name or '-'} — "
            f"{row.grams:.0f} г, {row.calories:.0f} ккал, source={row.source}"
        )
    await message.answer("\n".join(lines))
