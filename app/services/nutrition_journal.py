from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.repositories.nutrition import (
    create_meal_log,
    get_daily_meal_logs,
    upsert_daily_summary,
)


def user_local_date(user: User | None) -> datetime.date:
    tz_name = "Europe/Moscow"
    if user and user.profile and user.profile.timezone:
        tz_name = user.profile.timezone
    try:
        zone = ZoneInfo(tz_name)
    except Exception:
        zone = ZoneInfo("Europe/Moscow")
    return datetime.now(zone).date()


async def recalc_daily_summary(session: AsyncSession, user: User, day: datetime.date):
    logs = await get_daily_meal_logs(session, user.id, day)
    totals = {
        "calories_fact": sum(x.calories for x in logs),
        "protein_fact": sum(x.protein for x in logs),
        "fat_fact": sum(x.fat for x in logs),
        "carbs_fact": sum(x.carbs for x in logs),
        "fiber_fact": sum(x.fiber for x in logs),
        "sugar_fact": sum(x.sugar for x in logs),
        "sodium_mg_fact": sum(x.sodium_mg for x in logs),
        "water_ml_fact": sum(x.water_ml for x in logs),
        "calories_target": float(user.daily_calories_target or 2100),
        "protein_target": float(user.daily_protein_target or 120),
        "fat_target": float(user.daily_fat_target or 70),
        "carbs_target": float(user.daily_carbs_target or 250),
        "fiber_target": float(user.daily_fiber_target or 30),
        "water_target_ml": float(user.daily_water_target_ml or 2200),
    }
    totals["deficit_or_surplus"] = round(totals["calories_fact"] - totals["calories_target"], 2)
    summary = await upsert_daily_summary(session, user.id, day, totals)
    return summary, logs


async def add_manual_log(
    session: AsyncSession,
    user: User,
    payload: dict,
    meal_type: str = "snack",
    source: str = "manual",
    raw_input_text: str | None = None,
):
    day = user_local_date(user)
    await create_meal_log(
        session,
        user_id=user.id,
        date=day,
        meal_type=meal_type,
        product_id=payload.get("product_id"),
        dish_id=payload.get("dish_id"),
        custom_name=payload.get("custom_name"),
        grams=float(payload.get("grams", 0)),
        calories=float(payload.get("calories", 0)),
        protein=float(payload.get("protein", 0)),
        fat=float(payload.get("fat", 0)),
        carbs=float(payload.get("carbs", 0)),
        fiber=float(payload.get("fiber", 0)),
        sugar=float(payload.get("sugar", 0)),
        sodium_mg=float(payload.get("sodium_mg", 0)),
        water_ml=float(payload.get("water_ml", 0)),
        micronutrients_json=payload.get("micronutrients_json"),
        source=source,
        raw_input_text=raw_input_text,
    )
    return await recalc_daily_summary(session, user, day)
