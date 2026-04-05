from __future__ import annotations

import re
from typing import List, Optional

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Reminder, User
from app.services.user_profile import ensure_telegram_user

router = Router()

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def _list_keyboard(reminders: List[Reminder]) -> Optional[InlineKeyboardMarkup]:
    if not reminders:
        return None
    rows = [
        [
            InlineKeyboardButton(
                text=f"🗑 {r.hour:02d}:{r.minute:02d} · {r.title[:20]}",
                callback_data=f"rd:{r.id}",
            )
        ]
        for r in reminders
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("remind"))
async def cmd_remind(message: Message, command: CommandObject, session: AsyncSession):
    args = (command.args or "").strip()
    if not args:
        await message.answer(
            "Добавить напоминание:\n"
            "<code>/remind ЧЧ:ММ название</code>\n\n"
            "Пример: <code>/remind 08:30 завтрак</code>\n"
            "Время считается в твоём часовом поясе из профиля (по умолчанию Europe/Moscow). "
            "Сменить: <code>/timezone Europe/Berlin</code>",
            parse_mode="HTML",
        )
        return

    parts = args.split(maxsplit=1)
    time_raw = parts[0]
    title = parts[1].strip() if len(parts) > 1 else "Напоминание"

    m = _TIME_RE.match(time_raw)
    if not m:
        await message.answer("Не понял время. Формат: ЧЧ:ММ, например 08:30 или 9:05")
        return

    hour = int(m.group(1))
    minute = int(m.group(2))
    if hour > 23 or minute > 59:
        await message.answer("Некорректное время. Часы 0–23, минуты 0–59.")
        return

    user = await ensure_telegram_user(
        session,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    session.add(
        Reminder(
            user_id=user.id,
            chat_id=message.chat.id,
            hour=hour,
            minute=minute,
            title=title[:250],
            enabled=True,
        )
    )
    await session.flush()
    await message.answer(
        f"Ок, напоминание «{title}» на {hour:02d}:{minute:02d} сохранено.\n"
        f"Список: /reminders"
    )


@router.message(Command("reminders"))
async def cmd_reminders(message: Message, session: AsyncSession):
    user = await ensure_telegram_user(
        session,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    result = await session.execute(
        select(Reminder)
        .where(Reminder.user_id == user.id, Reminder.enabled.is_(True))
        .order_by(Reminder.hour, Reminder.minute)
    )
    items = list(result.scalars())
    if not items:
        await message.answer(
            "Пока нет напоминаний. Добавь: /remind 09:00 завтрак"
        )
        return
    lines = ["Твои напоминания (нажми, чтобы удалить):\n"]
    for r in items:
        lines.append(f"• {r.hour:02d}:{r.minute:02d} — {r.title}")
    await message.answer(
        "\n".join(lines),
        reply_markup=_list_keyboard(items),
    )


@router.callback_query(F.data.regexp(r"^rd:(\d+)$"))
async def on_reminder_delete(callback: CallbackQuery, session: AsyncSession):
    rid = int((callback.data or "").split(":")[1])
    result = await session.execute(
        select(Reminder, User)
        .join(User, Reminder.user_id == User.id)
        .where(Reminder.id == rid, User.telegram_id == callback.from_user.id)
    )
    row = result.first()
    if not row:
        await callback.answer("Не найдено", show_alert=True)
        return
    rem, _u = row
    await session.delete(rem)
    await session.flush()
    await callback.answer("Удалено")

    result2 = await session.execute(
        select(Reminder)
        .where(Reminder.user_id == _u.id, Reminder.enabled.is_(True))
        .order_by(Reminder.hour, Reminder.minute)
    )
    items = list(result2.scalars())
    if not items:
        await callback.message.edit_text("Напоминаний больше нет. Добавь: /remind 09:00 завтрак")
        return
    lines = ["Твои напоминания (нажми, чтобы удалить):\n"]
    for r in items:
        lines.append(f"• {r.hour:02d}:{r.minute:02d} — {r.title}")
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=_list_keyboard(items),
    )


@router.message(Command("timezone"))
async def cmd_timezone(message: Message, command: CommandObject, session: AsyncSession):
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    from app.services.user_profile import ensure_telegram_user, set_user_timezone

    await ensure_telegram_user(
        session,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )

    arg = (command.args or "").strip()
    if not arg:
        await message.answer(
            "Укажи IANA-часовой пояс, например:\n"
            "<code>/timezone Europe/Moscow</code>\n"
            "<code>/timezone Asia/Almaty</code>",
            parse_mode="HTML",
        )
        return
    try:
        ZoneInfo(arg)
    except ZoneInfoNotFoundError:
        await message.answer("Неизвестный пояс. Пример: Europe/Moscow")
        return

    ok = await set_user_timezone(session, message.from_user.id, arg)
    if not ok:
        await message.answer("Не удалось сохранить пояс. Напиши /start и попробуй снова.")
        return
    await message.answer(f"Часовой пояс сохранён: {arg}")
