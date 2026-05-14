from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import AIMemory, MealLog, User
from app.db.session import async_session_maker
from app.services.nutrition_ai import nutrition_periodic_report
from app.services.nutrition_calculator import aggregate_day

log = logging.getLogger(__name__)

REPORT_MEMORY_TYPE = "scheduled_report"
REPORT_MEMORY_KEY = "nutrition_8h_last_sent_at"


def _reports_enabled() -> bool:
    raw = (os.getenv("NUTRITION_REPORTS_ENABLED") or "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _report_interval_hours() -> int:
    raw = (os.getenv("NUTRITION_REPORT_INTERVAL_HOURS") or "8").strip()
    try:
        value = int(raw)
    except ValueError:
        return 8
    return max(1, value)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


async def nutrition_report_loop(bot: Bot, interval_sec: int = 600) -> None:
    if not _reports_enabled():
        log.info("periodic nutrition reports disabled")
        return

    while True:
        try:
            await _tick(bot)
        except Exception:
            log.exception("periodic nutrition report tick failed")
        await asyncio.sleep(interval_sec)


async def _tick(bot: Bot) -> None:
    hours = _report_interval_hours()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)

    async with async_session_maker() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.profile))
            .order_by(User.id.asc())
        )
        users = list(result.scalars())

    for user in users:
        await _send_report_if_due(bot, user.telegram_id, hours, cutoff, now)


async def _send_report_if_due(
    bot: Bot,
    telegram_id: int,
    hours: int,
    cutoff: datetime,
    now: datetime,
) -> None:
    async with async_session_maker() as session:
        user = (
            await session.execute(
                select(User)
                .options(selectinload(User.profile))
                .where(User.telegram_id == telegram_id)
            )
        ).scalar_one_or_none()
        if not user:
            return

        marker = (
            await session.execute(
                select(AIMemory).where(
                    AIMemory.user_id == user.id,
                    AIMemory.memory_type == REPORT_MEMORY_TYPE,
                    AIMemory.memory_key == REPORT_MEMORY_KEY,
                )
            )
        ).scalar_one_or_none()
        last_sent_at = _parse_dt(marker.memory_value if marker else None)
        if last_sent_at and now - last_sent_at < timedelta(hours=hours):
            return

        logs = list(
            (
                await session.execute(
                    select(MealLog)
                    .where(MealLog.user_id == user.id, MealLog.created_at >= cutoff)
                    .order_by(MealLog.created_at.asc())
                )
            ).scalars()
        )
        if not logs:
            return

        entries = [
            {
                "calories": row.calories,
                "protein": row.protein,
                "fat": row.fat,
                "carbs": row.carbs,
                "fiber": row.fiber,
                "sugar": row.sugar,
                "sodium_mg": row.sodium_mg,
                "water_ml": row.water_ml,
            }
            for row in logs
        ]
        totals = aggregate_day(entries)
        items = [
            {
                "time": row.created_at.isoformat() if row.created_at else "",
                "name": row.custom_name or "без названия",
                "grams": row.grams,
                "calories": row.calories,
                "protein": row.protein,
                "fat": row.fat,
                "carbs": row.carbs,
            }
            for row in logs
        ]
        text = await nutrition_periodic_report(totals, items, user, hours=hours)

        if marker is None:
            marker = AIMemory(
                user_id=user.id,
                memory_type=REPORT_MEMORY_TYPE,
                memory_key=REPORT_MEMORY_KEY,
                memory_value=now.isoformat(),
                importance=0.1,
            )
            session.add(marker)
        else:
            marker.memory_value = now.isoformat()

        await session.commit()

    try:
        await bot.send_message(
            telegram_id,
            f"Отчёт по питанию за последние {hours} ч:\n\n{text}",
        )
    except Exception:
        log.warning("failed to send periodic nutrition report to %s", telegram_id, exc_info=True)
