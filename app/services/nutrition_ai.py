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


async def nutrition_periodic_report(
    totals: dict[str, float],
    items: list[dict[str, Any]],
    user: User | None,
    hours: int = 8,
) -> str:
    targets = _targets_from_user(user)
    provider = get_ai_provider()
    payload = {
        "period_hours": hours,
        "items": items,
        "totals": totals,
        "daily_targets": targets,
        "goal": user.goal if user else "",
        "diet_type": user.diet_type if user else "",
    }
    if not provider:
        advice = _rule_based_advice(totals, targets)
        return (
            f"Анализ питания за последние {hours} ч:\n"
            f"Калории: {totals.get('calories', 0):.0f} ккал, "
            f"белки: {totals.get('protein', 0):.1f} г, "
            f"жиры: {totals.get('fat', 0):.1f} г, "
            f"углеводы: {totals.get('carbs', 0):.1f} г.\n\n"
            f"Что дальше:\n{advice}"
        )

    try:
        completion = await provider.client.chat.completions.create(
            model=provider.model,
            temperature=0.4,
            max_tokens=650,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Проанализируй питание пользователя за последние {hours} часов. "
                        "Коротко: 1) что уже съедено, 2) баланс БЖУ/калорий, "
                        "3) что лучше съесть в следующие 8 часов. "
                        "Не давай медицинских диагнозов. Используй только данные JSON:\n"
                        f"{json.dumps(payload, ensure_ascii=False)}"
                    ),
                },
            ],
        )
        text = (completion.choices[0].message.content or "").strip()
        if text:
            return text[:1500]
    except OpenAIError as exc:
        log.warning("periodic nutrition report fallback to rules: %s", exc)

    advice = _rule_based_advice(totals, targets)
    return (
        f"Анализ питания за последние {hours} ч:\n"
        f"Калории: {totals.get('calories', 0):.0f} ккал, "
        f"белки: {totals.get('protein', 0):.1f} г, "
        f"жиры: {totals.get('fat', 0):.1f} г, "
        f"углеводы: {totals.get('carbs', 0):.1f} г.\n\n"
        f"Что дальше:\n{advice}"
    )
