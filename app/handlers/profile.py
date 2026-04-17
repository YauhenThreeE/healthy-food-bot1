from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import User
from app.services.user_profile import ensure_telegram_user

router = Router()


def _format_profile_view(user: User) -> str:
    p = user.profile
    if not p or not p.goal:
        return (
            "👤 Твой профиль ещё не заполнен.\n\n"
            "Нажми /onboarding чтобы настроить."
        )
    return (
        f"👤 Профиль: {user.first_name or user.username or 'пользователь'}\n\n"
        f"🎯 Цель: {p.goal}\n"
        f"⚠️ Аллергии: {p.allergies or '—'}\n"
        f"🚫 Ограничения: {p.restrictions or '—'}\n"
        f"👨\u200d👩\u200d👧\u200d👦 Людей в семье: {p.household_size or '—'}\n"
        f"⏱ Время на готовку: {p.cooking_time or '—'}\n"
        f"💰 Бюджет: {p.budget or '—'}\n"
        f"🍳 Техника: {p.equipment or '—'}\n"
        f"🕐 Часовой пояс: {p.timezone or 'Europe/Moscow'}\n"
    )


def _profile_keyboard(has_profile: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_profile:
        rows.append([InlineKeyboardButton(
            text="✏️ Заполнить заново",
            callback_data="go:onboarding",
        )])
    else:
        rows.append([InlineKeyboardButton(
            text="📝 Заполнить профиль",
            callback_data="go:onboarding",
        )])
    rows.append([InlineKeyboardButton(
        text="🍽 Меню блюд",
        callback_data="go:menu",
    )])
    rows.append([InlineKeyboardButton(
        text="🛒 Оформить заказ",
        callback_data="go:order",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _get_user_with_profile(
    session: AsyncSession, telegram_id: int
) -> User | None:
    result = await session.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


@router.message(Command("profile"))
async def cmd_profile(message: Message, session: AsyncSession):
    u = message.from_user
    await ensure_telegram_user(session, u.id, u.username, u.first_name)
    user = await _get_user_with_profile(session, u.id)

    text = _format_profile_view(user)
    has_profile = bool(user and user.profile and user.profile.goal)
    await message.answer(text, reply_markup=_profile_keyboard(has_profile))


@router.callback_query(F.data == "go:profile")
async def on_go_profile(callback: CallbackQuery, session: AsyncSession):
    u = callback.from_user
    await ensure_telegram_user(session, u.id, u.username, u.first_name)
    user = await _get_user_with_profile(session, u.id)

    text = _format_profile_view(user)
    has_profile = bool(user and user.profile and user.profile.goal)
    await callback.message.edit_text(text, reply_markup=_profile_keyboard(has_profile))
    await callback.answer()
