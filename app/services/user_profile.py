from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, UserProfile


async def upsert_user_profile(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str],
    first_name: Optional[str],
    profile_data: dict,
) -> User:
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        try:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
            )
            session.add(user)
            await session.flush()
        except Exception:
            await session.rollback()
            result = await session.execute(
                select(User)
                .options(selectinload(User.profile))
                .where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one()

    if user.profile is None:
        user.profile = UserProfile()

    p = user.profile
    prev_tz = (p.timezone or "").strip() or None
    p.goal = profile_data.get("goal", "") or ""
    p.allergies = profile_data.get("allergies", "") or ""
    p.restrictions = profile_data.get("restrictions", "") or ""
    p.household_size = str(profile_data.get("household_size", "") or "")
    p.cooking_time = profile_data.get("cooking_time", "") or ""
    p.budget = profile_data.get("budget", "") or ""
    p.equipment = profile_data.get("equipment", "") or ""
    p.timezone = prev_tz or "Europe/Moscow"
    p.updated_at = datetime.now(timezone.utc)

    await session.flush()
    return user


async def get_user_by_telegram(session: AsyncSession, telegram_id: int) -> Optional[User]:
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def ensure_telegram_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str],
    first_name: Optional[str],
) -> User:
    user = await get_user_by_telegram(session, telegram_id)
    if user:
        return user
    try:
        user = User(telegram_id=telegram_id, username=username, first_name=first_name)
        session.add(user)
        await session.flush()
        return user
    except Exception:
        await session.rollback()
        user = await get_user_by_telegram(session, telegram_id)
        if user:
            return user
        raise


async def set_user_timezone(session: AsyncSession, telegram_id: int, tz_name: str) -> bool:
    user = await get_user_by_telegram(session, telegram_id)
    if not user:
        return False
    if user.profile is None:
        user.profile = UserProfile(timezone=tz_name)
    else:
        user.profile.timezone = tz_name
    user.profile.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return True


def format_profile_for_prompt(profile: Optional[UserProfile]) -> str:
    if not profile:
        return "Профиль не заполнен."
    return (
        f"Цель: {profile.goal}\n"
        f"Аллергии: {profile.allergies}\n"
        f"Ограничения: {profile.restrictions}\n"
        f"Людей кормить: {profile.household_size}\n"
        f"Время на готовку: {profile.cooking_time}\n"
        f"Бюджет: {profile.budget}\n"
        f"Техника: {profile.equipment}\n"
        f"Часовой пояс (напоминания): {profile.timezone}"
    )
