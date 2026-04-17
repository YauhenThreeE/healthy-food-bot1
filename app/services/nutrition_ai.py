from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAIError

from app.db.models import User
from app.services.ai_provider import get_ai_provider

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты ассистент по питанию. Отвечай по-русски, коротко, по делу, до 1200 символов. "
    "Никаких диагнозов, лечения или страшных формулировок."
)


def _rule_based_advice(totals: dict[str, float], targets: dict[str, float]) -> str:
    lines: list[str] = []
    if totals.get("protein", 0) < targets.get("protein", 0) * 0.85:
        lines.append("Белка маловато: добавь яйца, рыбу, творог, бобовые или курицу.")
    if totals.get("fiber", 0) < targets.get("fiber", 0) * 0.8:
        lines.append("Клетчатка ниже цели: добавь овощи, ягоды, овсянку, бобовые и яблоки.")
    if totals.get("calories", 0) > targets.get("calories", 0) * 1.1:
        lines.append("Калорий выше цели: сократи порции быстрых углеводов и жирных соусов.")
    if totals.get("water_ml", 0) < targets.get("water_ml", 0) * 0.75:
        lines.append("Воды мало: добери 2-3 стакана в течение дня.")
    if totals.get("vitamin_c", 0) < 25:
        lines.append("Витамин C низкий: добавь цитрусовые, киви, перец или брокколи.")
    if not lines:
        return "Рацион за день выглядит сбалансированно. Продолжай в том же стиле и следи за разнообразием."
    return "\n".join(f"• {item}" for item in lines)


def _targets_from_user(user: User | None) -> dict[str, float]:
    return {
        "calories": float(user.daily_calories_target or 2100),
        "protein": float(user.daily_protein_target or 120),
        "fat": float(user.daily_fat_target or 70),
        "carbs": float(user.daily_carbs_target or 250),
        "fiber": float(user.daily_fiber_target or 30),
        "water_ml": float(user.daily_water_target_ml or 2200),
    }


async def nutrition_advice_daily(
    totals: dict[str, float],
    user: User | None,
    memory_facts: list[dict[str, Any]] | None = None,
) -> str:
    targets = _targets_from_user(user)
    provider = get_ai_provider()
    if not provider:
        return _rule_based_advice(totals, targets)

    payload = {
        "totals": totals,
        "targets": targets,
        "goal": user.goal if user else "",
        "diet_type": user.diet_type if user else "",
        "memories": memory_facts or [],
    }
    try:
        completion = await provider.client.chat.completions.create(
            model=provider.model,
            temperature=0.5,
            max_tokens=500,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Сделай сжатый анализ рациона за сегодня и 3-5 практичных рекомендаций.\n"
                        "Используй только эти данные:\n"
                        f"{json.dumps(payload, ensure_ascii=False)}"
                    ),
                },
            ],
        )
        text = (completion.choices[0].message.content or "").strip()
        if not text:
            return _rule_based_advice(totals, targets)
        return text[:1200]
    except OpenAIError as exc:
        log.warning("nutrition advice fallback to rules: %s", exc)
        return _rule_based_advice(totals, targets)
