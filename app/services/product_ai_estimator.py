from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import OpenAIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Product
from app.repositories.nutrition import get_product_by_name
from app.services.ai_provider import get_ai_provider
from app.services.food_database import normalize_product_name
from app.services.nutrition_products import create_product_entry

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты справочник пищевой ценности.
Оцени БЖУ и калорийность продукта на 100 г съедобной части.
Верни только JSON без markdown и пояснений."""

REQUIRED_FLOAT_FIELDS = (
    "calories_100g",
    "protein_100g",
    "fat_100g",
    "carbs_100g",
    "fiber_100g",
    "sugar_100g",
    "sodium_mg_100g",
    "saturated_fat_100g",
    "water_ml_100g",
)

LIMITS = {
    "calories_100g": (0.0, 900.0),
    "protein_100g": (0.0, 100.0),
    "fat_100g": (0.0, 100.0),
    "carbs_100g": (0.0, 100.0),
    "fiber_100g": (0.0, 100.0),
    "sugar_100g": (0.0, 100.0),
    "sodium_mg_100g": (0.0, 5000.0),
    "saturated_fat_100g": (0.0, 100.0),
    "water_ml_100g": (0.0, 100.0),
}


def _extract_json(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _as_float(value: Any, field: str) -> float:
    low, high = LIMITS[field]
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return round(min(max(number, low), high), 2)


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _normalize_payload(product_name: str, data: dict[str, Any]) -> dict[str, Any]:
    name = normalize_product_name(str(data.get("name") or product_name))
    if not name:
        name = normalize_product_name(product_name)

    payload = {
        "name": name[:255],
        "brand": None,
        "category": str(data.get("category") or "ai_estimated")[:128],
        "micronutrients_json": {},
        "allergens_json": _as_dict(data.get("allergens_json")),
        "is_verified": False,
    }
    for field in REQUIRED_FLOAT_FIELDS:
        payload[field] = _as_float(data.get(field), field)
    return payload


async def estimate_and_create_product(
    session: AsyncSession,
    product_name: str,
) -> Product | None:
    normalized_name = normalize_product_name(product_name)
    if not normalized_name:
        return None

    existing = await get_product_by_name(session, normalized_name)
    if existing:
        return existing

    provider = get_ai_provider()
    if not provider:
        return None

    try:
        completion = await provider.client.chat.completions.create(
            model=provider.model,
            temperature=0.2,
            max_tokens=500,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Продукт: {normalized_name}\n"
                        "Верни JSON строго с полями: "
                        "name, category, calories_100g, protein_100g, fat_100g, "
                        "carbs_100g, fiber_100g, sugar_100g, sodium_mg_100g, "
                        "saturated_fat_100g, water_ml_100g, allergens_json. "
                        "Если продукт общий, оцени типичный вариант без бренда."
                    ),
                },
            ],
        )
    except OpenAIError as exc:
        log.warning("Could not estimate product nutrition via AI: %s", exc)
        return None

    content = completion.choices[0].message.content or ""
    data = _extract_json(content)
    if not data:
        log.warning("AI returned non-JSON nutrition estimate: %s", content[:500])
        return None

    payload = _normalize_payload(normalized_name, data)
    existing = await get_product_by_name(session, payload["name"])
    if existing:
        return existing
    return await create_product_entry(session, payload)
