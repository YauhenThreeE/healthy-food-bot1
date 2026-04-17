from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetInput:
    sex: str | None
    age: int | None
    height_cm: float | None
    weight_kg: float | None
    activity_level: str | None
    goal: str | None


def _activity_multiplier(activity_level: str | None) -> float:
    if not activity_level:
        return 1.3
    key = activity_level.lower().strip()
    mapping = {
        "low": 1.2,
        "sedentary": 1.2,
        "medium": 1.45,
        "moderate": 1.45,
        "high": 1.65,
        "active": 1.65,
    }
    return mapping.get(key, 1.3)


def estimate_daily_targets(data: TargetInput) -> dict[str, float]:
    weight = float(data.weight_kg or 70.0)
    height = float(data.height_cm or 170.0)
    age = int(data.age or 30)
    sex = (data.sex or "unknown").lower().strip()
    bmr = 10 * weight + 6.25 * height - 5 * age + (5 if sex == "male" else -161 if sex == "female" else -78)
    maintenance = bmr * _activity_multiplier(data.activity_level)

    goal = (data.goal or "").lower()
    if "похуд" in goal or "lose" in goal:
        calories = maintenance - 350
    elif "наб" in goal or "gain" in goal:
        calories = maintenance + 250
    else:
        calories = maintenance

    protein = weight * (1.8 if "наб" in goal or "gain" in goal else 1.5)
    fat = weight * 0.9
    carbs = max(120.0, (calories - (protein * 4 + fat * 9)) / 4)
    fiber = max(25.0, calories / 1000 * 14)
    water_ml = weight * 30

    return {
        "daily_calories_target": round(calories, 1),
        "daily_protein_target": round(protein, 1),
        "daily_fat_target": round(fat, 1),
        "daily_carbs_target": round(carbs, 1),
        "daily_fiber_target": round(fiber, 1),
        "daily_water_target_ml": round(water_ml, 1),
    }
