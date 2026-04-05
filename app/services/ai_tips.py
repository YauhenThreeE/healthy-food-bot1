from __future__ import annotations

import os
from typing import Optional

from openai import AsyncOpenAI

from app.services.user_profile import format_profile_for_prompt
from app.db.models import UserProfile


SYSTEM_PROMPT = """Ты дружелюбный нутрициолог-ассистент в Telegram-боте про здоровое питание.
Отвечай по-русски, кратко и по делу (до ~1200 символов), без диагнозов и без назначения лечения.
Учитывай аллергии и ограничения пользователя; если чего-то не хватает — мягко уточни в конце одним предложением.
Не выдумывай медицинские факты; давай общие рекомендации по питанию и бытовые идеи блюд."""


async def generate_tip(profile: Optional[UserProfile], user_question: Optional[str]) -> str:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return (
            "Ключ OpenAI не настроен. Добавь OPENAI_API_KEY в `.env` и перезапусти бота.\n"
            "Пока могу подсказать: заполни /onboarding и смотри /menu с идеями блюд."
        )

    client = AsyncOpenAI(api_key=api_key)
    ctx = format_profile_for_prompt(profile)
    user_msg = user_question.strip() if user_question else "Дай одну полезную рекомендацию на сегодня по питанию."
    completion = await client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Контекст профиля:\n{ctx}\n\nЗапрос пользователя:\n{user_msg}",
            },
        ],
        temperature=0.7,
        max_tokens=600,
    )
    text = (completion.choices[0].message.content or "").strip()
    return text or "Не удалось получить ответ. Попробуй ещё раз чуть позже."
