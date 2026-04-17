from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    OpenAIError,
    RateLimitError,
)

from app.services.user_profile import format_profile_for_prompt
from app.db.models import UserProfile

log = logging.getLogger(__name__)

GROQ_DEFAULT_BASE = "https://api.groq.com/openai/v1"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """Ты дружелюбный нутрициолог-ассистент в Telegram-боте про здоровое питание.
Отвечай по-русски, кратко и по делу (до ~1200 символов), без диагнозов и без назначения лечения.
Учитывай аллергии и ограничения пользователя; если чего-то не хватает — мягко уточни в конце одним предложением.
Не выдумывай медицинские факты; давай общие рекомендации по питанию и бытовые идеи блюд."""


def _provider_label(base_url: str) -> str:
    if "openrouter.ai" in base_url:
        return "OpenRouter"
    if "localhost" in base_url or "127.0.0.1" in base_url:
        return "Ollama"
    if "groq.com" in base_url:
        return "Groq"
    return "LLM-сервис"


def _llm_client_and_model() -> Tuple[Optional[AsyncOpenAI], Optional[str], str]:
    """
    Возвращает (client, model, label) или (None, None, "") если ключей нет.
    Приоритет: GROQ_API_KEY → OPENAI_API_KEY (совместимость).
    """
    groq_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if groq_key:
        base = (os.getenv("GROQ_BASE_URL") or GROQ_DEFAULT_BASE).strip()
        model = (os.getenv("GROQ_MODEL") or GROQ_DEFAULT_MODEL).strip()
        client = AsyncOpenAI(
            api_key=groq_key,
            base_url=base,
            timeout=90.0,
            max_retries=1,
        )
        return client, model, _provider_label(base)

    openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if openai_key:
        model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
        client = AsyncOpenAI(api_key=openai_key, timeout=90.0, max_retries=1)
        return client, model, "OpenAI"

    return None, None, ""


async def generate_tip(profile: Optional[UserProfile], user_question: Optional[str]) -> str:
    client, model, provider = _llm_client_and_model()
    if not client or not model:
        return (
            "Ключ для советов не настроен. Добавь в `.env` рядом с `bot.py`:\n"
            "• GROQ_API_KEY — ключ OpenRouter/Groq/Ollama-compatible сервиса;\n"
            "или\n"
            "• OPENAI_API_KEY — если остаёшься на OpenAI.\n\n"
            "Перезапусти бота. Пока могу: /onboarding и /menu."
        )

    ctx = format_profile_for_prompt(profile)
    user_msg = user_question.strip() if user_question else "Дай одну полезную рекомендацию на сегодня по питанию."

    try:
        completion = await client.chat.completions.create(
            model=model,
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
    except AuthenticationError as e:
        log.warning("%s authentication failed: %s", provider, e)
        if provider == "OpenRouter":
            return (
                "OpenRouter отклонил ключ (401). Проверь GROQ_API_KEY в `.env` "
                "и перезапусти бота."
            )
        if provider in {"Groq", "Ollama", "LLM-сервис"}:
            return (
                f"{provider} отклонил ключ (401). Проверь GROQ_API_KEY в `.env` "
                "и перезапусти бота."
            )
        return (
            "OpenAI отклонил ключ (401). Проверь OPENAI_API_KEY в `.env` и перезапусти бота."
        )
    except RateLimitError as e:
        log.warning("%s rate limit: %s", provider, e)
        if provider == "OpenRouter":
            return (
                "OpenRouter сейчас ограничил запросы к выбранной модели. "
                "Для free-моделей это часто значит, что провайдер временно перегружен. "
                "Подожди минуту или выбери другую модель в GROQ_MODEL."
            )
        return f"Слишком много запросов к {provider}. Подожди минуту и попробуй снова."
    except (APIConnectionError, APITimeoutError) as e:
        log.warning("%s network/timeout: %s", provider, e)
        return (
            f"Не удалось связаться с {provider} (сеть или таймаут). Проверь интернет и попробуй ещё раз."
        )
    except APIStatusError as e:
        log.warning("%s API error status=%s: %s", provider, getattr(e, "status_code", "?"), e)
        if provider == "OpenRouter":
            hint = "Проверь GROQ_MODEL в `.env` или выбери другую модель в OpenRouter."
        elif provider in {"Groq", "Ollama", "LLM-сервис"}:
            hint = "Проверь GROQ_MODEL и GROQ_BASE_URL в `.env`."
        else:
            hint = "Попробуй сменить OPENAI_MODEL в `.env`."
        return (
            f"Сервис советов вернул ошибку (код {getattr(e, 'status_code', '?')}). "
            f"{hint}"
        )
    except OpenAIError as e:
        log.warning("%s error: %s", provider, e)
        return f"Ошибка {provider}: {e!s}"
    except Exception:
        log.exception("Unexpected error in generate_tip")
        return "Произошла внутренняя ошибка при запросе совета. Попробуй позже."

    text = (completion.choices[0].message.content or "").strip()
    return text or "Не удалось получить ответ. Попробуй ещё раз чуть позже."
