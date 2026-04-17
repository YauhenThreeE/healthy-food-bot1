from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from app.services.food_database import ProductNutrients

_GRAM_PATTERNS = (
    re.compile(r"(?P<value>\d+(?:[.,]\d+)?)\s*(?:г|гр|грамм(?:а|ов)?)\b", re.IGNORECASE),
    re.compile(r"(?P<value>\d+(?:[.,]\d+)?)\s*(?:kg|кг)\b", re.IGNORECASE),
)
_COUNT_PATTERN = re.compile(r"(?P<count>\d+)\s+(?P<name>[а-яa-zё\s-]+)$", re.IGNORECASE)
_CLEANER = re.compile(r"[^\w\s\-]")
EGG_GRAMS = 55.0


@dataclass(frozen=True)
class ParsedMealInput:
    product: str
    grams: float


def _to_float(text: str) -> float:
    return float(text.replace(",", "."))


def parse_input(text: str) -> ParsedMealInput | None:
    if not text:
        return None
    raw = " ".join(text.strip().split())
    if not raw:
        return None

    grams = None
    product = raw
    for pattern in _GRAM_PATTERNS:
        match = pattern.search(raw)
        if not match:
            continue
        value = _to_float(match.group("value"))
        grams = value * (1000.0 if "кг" in match.group(0).lower() or "kg" in match.group(0).lower() else 1.0)
        product = (raw[: match.start()] + " " + raw[match.end() :]).strip()
        break

    normalized_product = _CLEANER.sub(" ", product).strip().lower()
    count_match = _COUNT_PATTERN.match(normalized_product)
    if count_match and grams is None:
        count = float(count_match.group("count"))
        name = count_match.group("name").strip()
        if "яйц" in name:
            return ParsedMealInput(product=name, grams=count * EGG_GRAMS)
        return ParsedMealInput(product=name, grams=count * 100.0)

    if not normalized_product:
        return None
    return ParsedMealInput(product=normalized_product, grams=grams or 100.0)


def calculate_nutrients(product: ProductNutrients, grams: float) -> dict[str, float]:
    scale = max(0.0, grams) / 100.0
    vitamins = product.vitamins
    return {
        "grams": round(grams, 2),
        "calories": round(product.calories * scale, 2),
        "protein": round(product.protein * scale, 2),
        "fat": round(product.fat * scale, 2),
        "carbs": round(product.carbs * scale, 2),
        "fiber": round(product.fiber * scale, 2),
        "sugar": round(product.sugar * scale, 2),
        "sodium_mg": round(product.sodium_mg * scale, 2),
        "water_ml": round(product.water_ml * scale, 2),
        "vitamin_a": round(vitamins.get("A", 0.0) * scale, 3),
        "vitamin_b": round(vitamins.get("B", 0.0) * scale, 3),
        "vitamin_c": round(vitamins.get("C", 0.0) * scale, 3),
        "vitamin_d": round(vitamins.get("D", 0.0) * scale, 3),
    }


def aggregate_day(entries: Iterable[dict[str, float]]) -> dict[str, float]:
    total = {
        "calories": 0.0,
        "protein": 0.0,
        "fat": 0.0,
        "carbs": 0.0,
        "fiber": 0.0,
        "sugar": 0.0,
        "sodium_mg": 0.0,
        "water_ml": 0.0,
        "vitamin_a": 0.0,
        "vitamin_b": 0.0,
        "vitamin_c": 0.0,
        "vitamin_d": 0.0,
    }
    for entry in entries:
        for key in total:
            total[key] += float(entry.get(key, 0.0) or 0.0)
    return {k: round(v, 2) for k, v in total.items()}
