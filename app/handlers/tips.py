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
from app.services.ai_memory import remember_fact
from app.services.ai_tips import generate_tip
from app.services.conversation_log import log_conversation_message
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


@router.message(Command("tip"))
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
        if not user:
            await message.answer("Сначала запусти /start, затем повтори запрос.")
            return
        if q and "не люблю" in q.lower():
            await remember_fact(
                session,
                user_id=user.id,
                memory_key="preference_dislike",
                memory_value=q,
                memory_type="preference",
                importance=0.7,
            )

        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            text = await generate_tip(profile, q)
        await log_conversation_message(session, user.id, "user", q or "/tip", intent="tip")
        for chunk in _split_for_telegram(text):
            await message.answer(chunk)
        await log_conversation_message(session, user.id, "assistant", text, intent="tip_reply")
    except Exception:
        log.exception("/tip handler failed")
        await message.answer(
            "Не удалось обработать команду. Проверь GROQ_API_KEY (или OPENAI_API_KEY) в `.env`, "
            "что запущен только один экземпляр бота, и попробуй снова."
        )
