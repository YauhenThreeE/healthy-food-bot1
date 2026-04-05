from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.services.ai_tips import generate_tip
from app.services.user_profile import ensure_telegram_user

router = Router()


@router.message(Command("tip"))
async def cmd_tip(message: Message, command: CommandObject, session: AsyncSession):
    await ensure_telegram_user(
        session,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    q = (command.args or "").strip() or None

    result = await session.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one_or_none()
    profile = user.profile if user else None

    text = await generate_tip(profile, q)
    await message.answer(text)
