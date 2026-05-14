from __future__ import annotations

import json
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.start import after_start_keyboard
from app.keyboards.survey import (
    survey_confirm_keyboard,
    survey_energy_keyboard,
    survey_meals_keyboard,
    survey_sleep_keyboard,
    survey_snacks_keyboard,
    survey_water_keyboard,
)
from app.services.ai_memory import remember_fact
from app.services.user_profile import ensure_telegram_user
from app.states.survey import SurveyStates

router = Router()

SURVEY_MEMORY_KEY = "healthy_food_survey"

_ENERGY_LABELS = {
    "good": "Энергии хватает",
    "afternoon_drop": "После обеда просадка",
    "tired": "Часто чувствую усталость",
}
_MEALS_LABELS = {
    "1_2": "1-2 раза",
    "3": "3 раза",
    "4_plus": "4+ раза",
    "irregular": "Нерегулярно",
}
_WATER_LABELS = {
    "low": "Меньше 1 литра",
    "medium": "1-2 литра",
    "high": "Больше 2 литров",
}
_SNACK_LABELS = {
    "rare": "Редко перекусываю",
    "sweet": "Сладкое / выпечка",
    "salty": "Соленое / фастфуд",
    "evening": "Чаще вечером",
}
_SLEEP_LABELS = {
    "under_6": "Меньше 6 часов",
    "6_7": "6-7 часов",
    "7_8": "7-8 часов",
    "over_8": "Больше 8 часов",
}


async def start_survey_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SurveyStates.energy)
    await message.answer(
        "Короткий опрос по питанию: 6 вопросов, чтобы советы были точнее.\n\n"
        "Как у тебя обычно с энергией в течение дня?",
        reply_markup=survey_energy_keyboard(),
    )


async def start_survey_from_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SurveyStates.energy)
    await callback.message.edit_text(
        "Короткий опрос по питанию: 6 вопросов, чтобы советы были точнее.\n\n"
        "Как у тебя обычно с энергией в течение дня?",
        reply_markup=survey_energy_keyboard(),
    )
    await callback.answer()


def _format_summary(data: dict) -> str:
    return (
        "Твои ответы:\n\n"
        f"Энергия: {data.get('energy', '-')}\n"
        f"Приемов пищи в день: {data.get('meals_per_day', '-')}\n"
        f"Вода: {data.get('water', '-')}\n"
        f"Перекусы: {data.get('snacks', '-')}\n"
        f"Сон: {data.get('sleep', '-')}\n"
        f"Главная сложность: {data.get('challenge', '-')}\n"
    )


@router.message(Command("survey"))
async def cmd_survey(message: Message, state: FSMContext):
    await start_survey_flow(message, state)


@router.callback_query(SurveyStates.energy, F.data.startswith("survey:energy:"))
async def survey_energy(callback: CallbackQuery, state: FSMContext):
    value = callback.data.rsplit(":", 1)[-1]
    await state.update_data(energy=_ENERGY_LABELS.get(value, "Не указано"))
    await state.set_state(SurveyStates.meals_per_day)
    await callback.message.edit_text(
        "Сколько раз в день ты обычно ешь?",
        reply_markup=survey_meals_keyboard(),
    )
    await callback.answer()


@router.callback_query(SurveyStates.meals_per_day, F.data.startswith("survey:meals:"))
async def survey_meals(callback: CallbackQuery, state: FSMContext):
    value = callback.data.rsplit(":", 1)[-1]
    await state.update_data(meals_per_day=_MEALS_LABELS.get(value, "Не указано"))
    await state.set_state(SurveyStates.water)
    await callback.message.edit_text(
        "Сколько воды обычно пьешь за день?",
        reply_markup=survey_water_keyboard(),
    )
    await callback.answer()


@router.callback_query(SurveyStates.water, F.data.startswith("survey:water:"))
async def survey_water(callback: CallbackQuery, state: FSMContext):
    value = callback.data.rsplit(":", 1)[-1]
    await state.update_data(water=_WATER_LABELS.get(value, "Не указано"))
    await state.set_state(SurveyStates.snacks)
    await callback.message.edit_text(
        "Какие перекусы чаще всего бывают?",
        reply_markup=survey_snacks_keyboard(),
    )
    await callback.answer()


@router.callback_query(SurveyStates.snacks, F.data.startswith("survey:snacks:"))
async def survey_snacks(callback: CallbackQuery, state: FSMContext):
    value = callback.data.rsplit(":", 1)[-1]
    await state.update_data(snacks=_SNACK_LABELS.get(value, "Не указано"))
    await state.set_state(SurveyStates.sleep)
    await callback.message.edit_text(
        "Сколько часов ты обычно спишь?",
        reply_markup=survey_sleep_keyboard(),
    )
    await callback.answer()


@router.callback_query(SurveyStates.sleep, F.data.startswith("survey:sleep:"))
async def survey_sleep(callback: CallbackQuery, state: FSMContext):
    value = callback.data.rsplit(":", 1)[-1]
    await state.update_data(sleep=_SLEEP_LABELS.get(value, "Не указано"))
    await state.set_state(SurveyStates.challenge)
    await callback.message.edit_text(
        "Что сейчас сложнее всего в питании?\n\n"
        "Напиши одним сообщением. Например: поздние ужины, сладкое, нет времени готовить."
    )
    await callback.answer()


@router.message(SurveyStates.challenge, F.text, ~F.text.startswith("/"))
async def survey_challenge(message: Message, state: FSMContext):
    await state.update_data(challenge=message.text.strip())
    data = await state.get_data()
    await state.set_state(SurveyStates.confirm)
    await message.answer(
        _format_summary(data) + "\nСохранить ответы?",
        reply_markup=survey_confirm_keyboard(),
    )


@router.callback_query(SurveyStates.confirm, F.data == "survey:confirm:save")
async def survey_save(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    user = await ensure_telegram_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
    )
    payload = {
        **data,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await remember_fact(
        session=session,
        user_id=user.id,
        memory_key=SURVEY_MEMORY_KEY,
        memory_value=json.dumps(payload, ensure_ascii=False),
        memory_type="survey",
        importance=0.8,
    )
    await session.commit()
    await state.clear()
    await callback.message.edit_text(
        "Опрос сохранен.\n\n"
        "Теперь советы по питанию смогут учитывать эти ответы.",
        reply_markup=after_start_keyboard(show_profile=True),
    )
    await callback.answer()


@router.callback_query(SurveyStates.confirm, F.data == "survey:confirm:restart")
async def survey_restart(callback: CallbackQuery, state: FSMContext):
    await start_survey_from_callback(callback, state)
