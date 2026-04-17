from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Dish, User
from app.repositories.nutrition import (
    find_products_mentioned_in_text,
    get_daily_meal_logs,
    get_product_by_name,
    search_products,
)
from app.services.ai_memory import load_memory_context, remember_fact
from app.services.conversation_log import log_conversation_message
from app.services.food_database import lookup_product, supported_products
from app.services.meal_text_parser import parse_free_text_meal
from app.services.nutrition_ai import nutrition_advice_daily
from app.services.nutrition_calculator import aggregate_day, calculate_nutrients, parse_input
from app.services.nutrition_journal import add_manual_log, user_local_date
from app.services.nutrition_products import nutrition_for_grams
from app.services.product_ai_estimator import estimate_and_create_product
from app.services.user_profile import ensure_telegram_user

router = Router()


def _clean_log_food_args(args: str) -> str:
    command_markers = ("/log_food", "/log_meal")
    cleaned = args.strip()
    for marker in command_markers:
        index = cleaned.find(marker)
        if index > 0:
            cleaned = cleaned[:index].strip()
    return cleaned


def _fmt_daily_line(name: str, fact: float, target: float, unit: str) -> str:
    target_text = f"{target:.0f}" if target > 0 else "—"
    return f"{name}: {fact:.1f} {unit} / {target_text} {unit}"


async def _get_user(session: AsyncSession, tg_user) -> User | None:
    await ensure_telegram_user(session, tg_user.id, tg_user.username, tg_user.first_name)
    result = await session.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.telegram_id == tg_user.id)
    )
    return result.scalar_one_or_none()


async def _resolve_nutrition_entry(
    session: AsyncSession,
    text: str,
) -> tuple[dict | None, str | None]:
    parsed = parse_input(text)
    if not parsed:
        return None, "Не удалось разобрать ввод. Пример: /log_food курица 200 г"

    db_product = await get_product_by_name(session, parsed.product)
    if db_product:
        macros = nutrition_for_grams(db_product, parsed.grams)
        payload = {
            "product_id": db_product.id,
            "custom_name": db_product.name,
            **macros,
        }
        return payload, None

    db_matches = await search_products(session, parsed.product, limit=3)
    if len(db_matches) == 1:
        db_product = db_matches[0]
        macros = nutrition_for_grams(db_product, parsed.grams)
        payload = {
            "product_id": db_product.id,
            "custom_name": db_product.name,
            **macros,
        }
        return payload, None

    static_product = lookup_product(parsed.product)
    if static_product:
        macros = calculate_nutrients(static_product, parsed.grams)
        payload = {
            "custom_name": static_product.name,
            "grams": macros["grams"],
            "calories": macros["calories"],
            "protein": macros["protein"],
            "fat": macros["fat"],
            "carbs": macros["carbs"],
            "fiber": macros["fiber"],
            "sugar": macros["sugar"],
            "sodium_mg": macros["sodium_mg"],
            "water_ml": macros["water_ml"],
            "micronutrients_json": {
                "vitamin_a": macros["vitamin_a"],
                "vitamin_b": macros["vitamin_b"],
                "vitamin_c": macros["vitamin_c"],
                "vitamin_d": macros["vitamin_d"],
            },
        }
        return payload, None

    dish = (
        await session.execute(
            select(Dish).where(Dish.name.ilike(f"%{parsed.product}%")).limit(1)
        )
    ).scalar_one_or_none()
    if dish:
        weight = dish.total_weight_g or 100.0
        factor = parsed.grams / weight
        payload = {
            "dish_id": dish.id,
            "custom_name": dish.name,
            "grams": parsed.grams,
            "calories": round(float(dish.calories_total or dish.calories or 0) * factor, 2),
            "protein": round(float(dish.protein_total or 0) * factor, 2),
            "fat": round(float(dish.fat_total or 0) * factor, 2),
            "carbs": round(float(dish.carbs_total or 0) * factor, 2),
            "fiber": round(float(dish.fiber_total or 0) * factor, 2),
            "sugar": round(float(dish.sugar_total or 0) * factor, 2),
            "sodium_mg": round(float(dish.sodium_mg_total or 0) * factor, 2),
            "water_ml": round(float(dish.water_ml_total or 0) * factor, 2),
            "micronutrients_json": dict(dish.micronutrients_json or {}),
        }
        return payload, None

    estimate = await estimate_and_create_product(session, parsed.product)
    if estimate.product:
        macros = nutrition_for_grams(estimate.product, parsed.grams)
        payload = {
            "product_id": estimate.product.id,
            "custom_name": estimate.product.name,
            "estimated_by_ai": True,
            **macros,
        }
        return payload, None

    mentioned_products = await find_products_mentioned_in_text(session, parsed.product, limit=1)
    if mentioned_products:
        db_product = mentioned_products[0]
        macros = nutrition_for_grams(db_product, parsed.grams)
        payload = {
            "product_id": db_product.id,
            "custom_name": parsed.product,
            "matched_base_product": db_product.name,
            "ai_error": estimate.error,
            **macros,
        }
        return payload, None

    suggestions = [product.name for product in db_matches]
    suggestions.extend(name for name in supported_products() if name not in suggestions)
    return None, (
        f"ИИ не смог оценить продукт: {estimate.error or 'нет ответа'}.\n\n"
        "Продукт не найден в локальной базе. Сейчас лучше писать базовый продукт и вес, например:\n"
        "• /log_food банан 1 шт\n"
        "• /log_food курица 200 г\n"
        "• /log_food гречка 150 г\n\n"
        f"Доступные продукты: {', '.join(suggestions[:10])}."
    )


@router.message(Command("log_food", "log_meal"))
async def cmd_log_food(message: Message, command: CommandObject, session: AsyncSession):
    args = _clean_log_food_args(command.args or "")
    if not args:
        await message.answer("Напиши еду и вес: /log_food курица 200 г")
        return
    user = await _get_user(session, message.from_user)
    if not user:
        await message.answer("Не удалось найти пользователя, попробуй /start")
        return

    payload, error = await _resolve_nutrition_entry(session, args)
    if error:
        await message.answer(error)
        return

    summary, _ = await add_manual_log(
        session=session,
        user=user,
        payload=payload,
        meal_type="snack",
        source=(
            "ai_estimated"
            if payload.get("estimated_by_ai")
            else "base_product_fallback"
            if payload.get("matched_base_product")
            else "manual"
        ),
        raw_input_text=args,
    )
    await log_conversation_message(session, user.id, "user", args, intent="log_food")
    await log_conversation_message(
        session,
        user.id,
        "assistant",
        f"Logged {payload.get('custom_name')} {payload.get('grams')}g",
        intent="log_food_result",
    )

    notes = []
    if payload.get("estimated_by_ai"):
        notes.append("• Пищевая ценность оценена ИИ, проверь при необходимости.")
    if payload.get("matched_base_product"):
        notes.append(f"• Расчёт сделан по базовому продукту: {payload['matched_base_product']}.")
    if payload.get("ai_error"):
        notes.append(f"• ИИ не смог оценить блюдо: {payload['ai_error']}.")
    notes_text = ("\n" + "\n".join(notes)) if notes else ""
    await message.answer(
        "Добавлено в дневник:\n"
        f"• {payload.get('custom_name')} — {payload.get('grams', 0):.0f} г\n"
        f"• {payload.get('calories', 0):.1f} ккал"
        f"{notes_text}\n\n"
        f"Текущий итог дня: {summary.calories_fact:.1f} / {summary.calories_target:.0f} ккал"
    )


@router.message(Command("today", "summary"))
async def cmd_today(message: Message, session: AsyncSession):
    user = await _get_user(session, message.from_user)
    if not user:
        await message.answer("Не удалось найти пользователя, попробуй /start")
        return
    day = user_local_date(user)
    logs = await get_daily_meal_logs(session, user.id, day)
    if not logs:
        await message.answer("Сегодня пока нет записей. Добавь: /log_food яблоко 180 г")
        return

    vitamins_total = {"vitamin_a": 0.0, "vitamin_b": 0.0, "vitamin_c": 0.0, "vitamin_d": 0.0}
    entries = []
    for row in logs:
        entries.append(
            {
                "calories": row.calories,
                "protein": row.protein,
                "fat": row.fat,
                "carbs": row.carbs,
                "fiber": row.fiber,
                "sugar": row.sugar,
                "sodium_mg": row.sodium_mg,
                "water_ml": row.water_ml,
            }
        )
        micron = dict(row.micronutrients_json or {})
        for key in vitamins_total:
            vitamins_total[key] += float(micron.get(key, 0.0))
    totals = aggregate_day(entries)

    lines = ["Сегодня съедено:"]
    for row in logs[-10:]:
        lines.append(f"• {row.custom_name or 'Без названия'} — {row.grams:.0f} г ({row.calories:.0f} ккал)")
    lines.append("")
    lines.append(_fmt_daily_line("Калории", totals["calories"], float(user.daily_calories_target or 2100), "ккал"))
    lines.append(_fmt_daily_line("Белки", totals["protein"], float(user.daily_protein_target or 120), "г"))
    lines.append(_fmt_daily_line("Жиры", totals["fat"], float(user.daily_fat_target or 70), "г"))
    lines.append(_fmt_daily_line("Углеводы", totals["carbs"], float(user.daily_carbs_target or 250), "г"))
    lines.append(_fmt_daily_line("Клетчатка", totals["fiber"], float(user.daily_fiber_target or 30), "г"))
    lines.append(_fmt_daily_line("Вода", totals["water_ml"], float(user.daily_water_target_ml or 2200), "мл"))
    lines.append(
        "Витамины (оценочно): "
        f"A {vitamins_total['vitamin_a']:.2f}, "
        f"B {vitamins_total['vitamin_b']:.2f}, "
        f"C {vitamins_total['vitamin_c']:.2f}, "
        f"D {vitamins_total['vitamin_d']:.2f}"
    )
    await message.answer("\n".join(lines))


@router.message(Command("advice"))
async def cmd_advice(message: Message, session: AsyncSession):
    user = await _get_user(session, message.from_user)
    if not user:
        await message.answer("Не удалось найти пользователя, попробуй /start")
        return
    day = user_local_date(user)
    logs = await get_daily_meal_logs(session, user.id, day)
    if not logs:
        await message.answer("Чтобы получить рекомендации, сначала добавь хотя бы один приём пищи: /log_food")
        return

    totals = aggregate_day(
        {
            "calories": x.calories,
            "protein": x.protein,
            "fat": x.fat,
            "carbs": x.carbs,
            "fiber": x.fiber,
            "sugar": x.sugar,
            "sodium_mg": x.sodium_mg,
            "water_ml": x.water_ml,
            "vitamin_a": float((x.micronutrients_json or {}).get("vitamin_a", 0)),
            "vitamin_b": float((x.micronutrients_json or {}).get("vitamin_b", 0)),
            "vitamin_c": float((x.micronutrients_json or {}).get("vitamin_c", 0)),
            "vitamin_d": float((x.micronutrients_json or {}).get("vitamin_d", 0)),
        }
        for x in logs
    )
    memory = await load_memory_context(session, user.id, limit=8)
    advice_text = await nutrition_advice_daily(totals, user=user, memory_facts=memory)
    await log_conversation_message(session, user.id, "assistant", advice_text, intent="daily_advice")
    await message.answer(advice_text)


@router.message(Command("remember"))
async def cmd_remember(message: Message, command: CommandObject, session: AsyncSession):
    user = await _get_user(session, message.from_user)
    if not user:
        await message.answer("Не удалось найти пользователя.")
        return
    args = (command.args or "").strip()
    if "=" not in args:
        await message.answer("Формат: /remember ключ=значение\nПример: /remember dislikes=молоко")
        return
    key, value = [x.strip() for x in args.split("=", 1)]
    if not key or not value:
        await message.answer("Заполни и ключ, и значение.")
        return
    await remember_fact(session, user.id, memory_key=key, memory_value=value)
    await message.answer(f"Запомнил: {key} = {value}")


@router.message(Command("parse_meal"))
async def cmd_parse_meal(message: Message, command: CommandObject):
    args = (command.args or "").strip()
    if not args:
        await message.answer("Пример: /parse_meal Я съел овсянку с молоком, 2 яйца и яблоко")
        return
    parsed = parse_free_text_meal(args)
    items = parsed.get("items", [])
    if not items:
        await message.answer("Не удалось выделить продукты из текста.")
        return
    lines = ["Что удалось распознать:"]
    for item in items:
        lines.append(
            f"• {item['product_name']} ~ {item['grams']:.0f} г "
            f"(confidence {item['confidence']:.2f})"
        )
    await message.answer("\n".join(lines))
