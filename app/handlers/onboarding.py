from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.states.onboarding import OnboardingStates
from app.services.user_profile import upsert_user_profile
from app.keyboards.onboarding import (
    goal_keyboard,
    yes_no_keyboard,
    cooking_time_keyboard,
    budget_keyboard,
    confirm_keyboard,
)
from app.keyboards.start import after_start_keyboard

router = Router()


def format_profile(data: dict) -> str:
    return (
        "Вот твой профиль:\n\n"
        f"🎯 Цель: {data.get('goal', '-')}\n"
        f"⚠️ Аллергии: {data.get('allergies', '-')}\n"
        f"🚫 Ограничения: {data.get('restrictions', '-')}\n"
        f"👨‍👩‍👧‍👦 Людей в семье: {data.get('household_size', '-')}\n"
        f"⏱ Время на готовку: {data.get('cooking_time', '-')}\n"
        f"💰 Бюджет: {data.get('budget', '-')}\n"
        f"🍳 Техника: {data.get('equipment', '-')}\n"
    )


@router.message(F.text == "/onboarding")
async def start_onboarding(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(OnboardingStates.goal)
    await message.answer(
        "Давай настроим твой профиль питания.\n\n"
        "Какая у тебя главная цель?",
        reply_markup=goal_keyboard(),
    )


@router.callback_query(OnboardingStates.goal, F.data.startswith("goal_"))
async def onboarding_goal(callback: CallbackQuery, state: FSMContext):
    goal_map = {
        "goal_lose_weight": "Похудеть",
        "goal_maintain": "Поддерживать форму",
        "goal_gain": "Набрать массу",
        "goal_clean_eating": "Питаться чище",
        "goal_family": "Семейное питание",
    }

    goal_value = goal_map.get(callback.data, "Не указано")
    await state.update_data(goal=goal_value)
    await state.set_state(OnboardingStates.allergies)

    await callback.message.edit_text(
        "Есть ли у тебя аллергии?",
        reply_markup=yes_no_keyboard("allergies"),
    )
    await callback.answer()


@router.callback_query(OnboardingStates.allergies, F.data == "allergies_no")
async def allergies_no(callback: CallbackQuery, state: FSMContext):
    await state.update_data(allergies="Нет")
    await state.set_state(OnboardingStates.restrictions)
    await callback.message.edit_text(
        "Напиши, что ты не ешь или чего хочешь избегать.\n\n"
        "Пример: сахар, молочка, свинина, глютен.\n"
        "Если ограничений нет — напиши: нет"
    )
    await callback.answer()


@router.callback_query(OnboardingStates.allergies, F.data == "allergies_yes")
async def allergies_yes(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Напиши аллергии одним сообщением.\n\n"
        "Пример: орехи, лактоза, морепродукты"
    )
    await callback.answer()


@router.message(OnboardingStates.allergies, F.text, ~F.text.startswith("/"))
async def allergies_text(message: Message, state: FSMContext):
    text = message.text.strip()
    await state.update_data(allergies=text)
    await state.set_state(OnboardingStates.restrictions)
    await message.answer(
        "Теперь напиши, что ты не ешь или чего хочешь избегать.\n\n"
        "Пример: сахар, молочка, свинина, глютен.\n"
        "Если ограничений нет — напиши: нет"
    )


@router.message(OnboardingStates.restrictions, F.text, ~F.text.startswith("/"))
async def restrictions_step(message: Message, state: FSMContext):
    await state.update_data(restrictions=message.text.strip())
    await state.set_state(OnboardingStates.household_size)
    await message.answer("Сколько человек обычно нужно кормить? Напиши число.")


@router.message(OnboardingStates.household_size, F.text, ~F.text.startswith("/"))
async def household_step(message: Message, state: FSMContext):
    text = message.text.strip()

    if not text.isdigit():
        await message.answer("Напиши число. Например: 1, 2, 3")
        return

    await state.update_data(household_size=text)
    await state.set_state(OnboardingStates.cooking_time)
    await message.answer(
        "Сколько времени ты готов тратить на готовку?",
        reply_markup=cooking_time_keyboard(),
    )


@router.callback_query(OnboardingStates.cooking_time, F.data.startswith("cooking_"))
async def cooking_time_step(callback: CallbackQuery, state: FSMContext):
    cooking_map = {
        "cooking_15": "До 15 минут",
        "cooking_30": "До 30 минут",
        "cooking_45": "30–45 минут",
    }

    await state.update_data(cooking_time=cooking_map.get(callback.data, "Не указано"))
    await state.set_state(OnboardingStates.budget)
    await callback.message.edit_text(
        "Какой у тебя ориентир по бюджету?",
        reply_markup=budget_keyboard(),
    )
    await callback.answer()


@router.callback_query(OnboardingStates.budget, F.data.startswith("budget_"))
async def budget_step(callback: CallbackQuery, state: FSMContext):
    budget_map = {
        "budget_low": "Эконом",
        "budget_medium": "Средний",
        "budget_high": "Выше среднего",
    }

    await state.update_data(budget=budget_map.get(callback.data, "Не указано"))
    await state.set_state(OnboardingStates.equipment)
    await callback.message.edit_text(
        "Какая техника у тебя есть дома?\n\n"
        "Напиши одним сообщением.\n"
        "Пример: духовка, плита, аэрогриль, блендер"
    )
    await callback.answer()


@router.message(OnboardingStates.equipment, F.text, ~F.text.startswith("/"))
async def equipment_step(message: Message, state: FSMContext):
    await state.update_data(equipment=message.text.strip())
    data = await state.get_data()

    await state.set_state(OnboardingStates.confirm)
    await message.answer(
        format_profile(data) + "\nВсе верно?",
        reply_markup=confirm_keyboard(),
    )


@router.callback_query(OnboardingStates.confirm, F.data == "confirm_yes")
async def confirm_yes(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    u = callback.from_user
    await upsert_user_profile(
        session,
        telegram_id=u.id,
        username=u.username,
        first_name=u.first_name,
        profile_data=data,
    )

    await callback.message.edit_text(
        "Профиль сохранен ✅\n\n"
        f"{format_profile(data)}\n"
        "Что дальше?",
        reply_markup=after_start_keyboard(show_profile=True),
    )
    await state.clear()
    await callback.answer()


@router.callback_query(OnboardingStates.confirm, F.data == "confirm_restart")
async def confirm_restart(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(OnboardingStates.goal)
    await callback.message.edit_text(
        "Начнем заново.\n\nКакая у тебя главная цель?",
        reply_markup=goal_keyboard(),
    )
    await callback.answer()
