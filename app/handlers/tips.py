from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.services.ai_tips import generate_tip
from app.services.user_profile import ensure_telegram_user

router = Router()
log = logging.getLogger(__name__)

_MAX_LEN = 4000


def _split_for_telegram(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return ["Пустой ответ от модели. Попробуй ещё раз или переформулируй вопрос."]
    if len(text) <= _MAX_LEN:
        return [text]
    parts: list[str] = []
    while text:
        parts.append(text[:_MAX_LEN])
        text = text[_MAX_LEN:].lstrip()
    return [p for p in parts if p] or ["Не удалось разбить ответ на сообщения."]


@router.message(Command("tip", "advice"))
async def cmd_tip(message: Message, command: CommandObject, session: AsyncSession):
    try:
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

        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            text = await generate_tip(profile, q)
        for chunk in _split_for_telegram(text):
            await message.answer(chunk)
    except Exception:
        log.exception("/tip handler failed")
        await message.answer(
            "Не удалось обработать команду. Проверь GROQ_API_KEY (или OPENAI_API_KEY) в `.env`, "
            "что запущен только один экземпляр бота, и попробуй снова."
        )
