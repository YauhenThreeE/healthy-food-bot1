from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import async_session_maker
from app.db.models import Reminder, User

log = logging.getLogger(__name__)


@dataclass
class _ReminderSnapshot:
    id: int
    chat_id: int
    hour: int
    minute: int
    title: str
    last_fired_on: Optional[date]
    tz_name: str


async def reminder_loop(bot: Bot, interval_sec: int = 30) -> None:
    while True:
        try:
            await _tick(bot)
        except Exception:
            log.exception("reminder tick failed")
        await asyncio.sleep(interval_sec)


async def _tick(bot: Bot) -> None:
    snapshots: list[_ReminderSnapshot] = []
    async with async_session_maker() as session:
        result = await session.execute(
            select(Reminder)
            .where(Reminder.enabled.is_(True))
            .options(selectinload(Reminder.user).selectinload(User.profile))
        )
        for r in result.scalars().unique():
            tz_name = "Europe/Moscow"
            if r.user and r.user.profile and r.user.profile.timezone:
                tz_name = r.user.profile.timezone
            snapshots.append(
                _ReminderSnapshot(
                    id=r.id,
                    chat_id=r.chat_id,
                    hour=r.hour,
                    minute=r.minute,
                    title=r.title,
                    last_fired_on=r.last_fired_on,
                    tz_name=tz_name,
                )
            )

    for snap in snapshots:
        try:
            tz = ZoneInfo(snap.tz_name)
        except ZoneInfoNotFoundError:
            tz = ZoneInfo("Europe/Moscow")
        now_local = datetime.now(tz)
        if now_local.hour != snap.hour or now_local.minute != snap.minute:
            continue
        today: date = now_local.date()
        if snap.last_fired_on == today:
            continue

        text = f"⏰ Напоминание: {snap.title}"
        try:
            await bot.send_message(chat_id=snap.chat_id, text=text)
        except Exception:
            log.warning("failed to send reminder id=%s chat=%s", snap.id, snap.chat_id, exc_info=True)
            continue

        async with async_session_maker() as session:
            row = await session.get(Reminder, snap.id)
            if row:
                row.last_fired_on = today
                await session.commit()
