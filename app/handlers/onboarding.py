from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.states.onboarding import OnboardingStates
from app.services.user_profile import upsert_user_profile
from app.keyboards.onboarding import (
    activity_keyboard,
    goal_keyboard,
    diet_type_keyboard,
    sex_keyboard,
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
        f"⚧ Пол: {data.get('sex', '-')}\n"
        f"🎂 Возраст: {data.get('age', '-')}\n"
        f"📏 Рост: {data.get('height_cm', '-')} см\n"
        f"⚖️ Вес: {data.get('weight_kg', '-')} кг\n"
        f"🏃 Активность: {data.get('activity_level', '-')}\n"
        f"🥗 Тип питания: {data.get('diet_type', '-')}\n"
        f"⚠️ Аллергии: {data.get('allergies', '-')}\n"
        f"🚫 Исключенные продукты: {data.get('excluded_products', '-')}\n"
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
    await state.set_state(OnboardingStates.sex)

    await callback.message.edit_text(
        "Укажи пол (для расчёта дневных ориентиров):",
        reply_markup=sex_keyboard(),
    )
    await callback.answer()


@router.callback_query(OnboardingStates.sex, F.data.startswith("sex_"))
async def onboarding_sex(callback: CallbackQuery, state: FSMContext):
    sex_map = {
        "sex_female": "female",
        "sex_male": "male",
        "sex_unknown": "unknown",
    }
    await state.update_data(sex=sex_map.get(callback.data, "unknown"))
    await state.set_state(OnboardingStates.age)
    await callback.message.edit_text("Сколько тебе лет? Напиши число.")
    await callback.answer()


@router.message(OnboardingStates.age, F.text, ~F.text.startswith("/"))
async def onboarding_age(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or not (12 <= int(text) <= 99):
        await message.answer("Возраст должен быть числом от 12 до 99.")
        return
    await state.update_data(age=int(text))
    await state.set_state(OnboardingStates.height_cm)
    await message.answer("Рост в сантиметрах? Например: 175")


@router.message(OnboardingStates.height_cm, F.text, ~F.text.startswith("/"))
async def onboarding_height(message: Message, state: FSMContext):
    text = message.text.strip().replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        await message.answer("Напиши рост числом, например: 175")
        return
    if value < 120 or value > 230:
        await message.answer("Рост должен быть в диапазоне 120-230 см.")
        return
    await state.update_data(height_cm=value)
    await state.set_state(OnboardingStates.weight_kg)
    await message.answer("Текущий вес в кг? Например: 68")


@router.message(OnboardingStates.weight_kg, F.text, ~F.text.startswith("/"))
async def onboarding_weight(message: Message, state: FSMContext):
    text = message.text.strip().replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        await message.answer("Напиши вес числом, например: 68")
        return
    if value < 30 or value > 300:
        await message.answer("Вес должен быть в диапазоне 30-300 кг.")
        return
    await state.update_data(weight_kg=value, target_weight_kg=value)
    await state.set_state(OnboardingStates.activity_level)
    await message.answer(
        "Какой уровень активности у тебя обычно?",
        reply_markup=activity_keyboard(),
    )


@router.callback_query(OnboardingStates.activity_level, F.data.startswith("activity_"))
async def onboarding_activity(callback: CallbackQuery, state: FSMContext):
    activity_map = {
        "activity_low": "low",
        "activity_medium": "medium",
        "activity_high": "high",
    }
    await state.update_data(activity_level=activity_map.get(callback.data, "medium"))
    await state.set_state(OnboardingStates.diet_type)
    await callback.message.edit_text(
        "Какой тип питания тебе ближе?",
        reply_markup=diet_type_keyboard(),
    )
    await callback.answer()


@router.callback_query(OnboardingStates.diet_type, F.data.startswith("diet_"))
async def onboarding_diet_type(callback: CallbackQuery, state: FSMContext):
    diet_map = {
        "diet_balanced": "balanced",
        "diet_vegetarian": "vegetarian",
        "diet_vegan": "vegan",
        "diet_lowcarb": "lowcarb",
    }
    await state.update_data(diet_type=diet_map.get(callback.data, "balanced"))
    await state.set_state(OnboardingStates.allergies)
    await callback.message.edit_text(
        "Есть ли у тебя аллергии?",
        reply_markup=yes_no_keyboard("allergies"),
    )
    await callback.answer()


@router.callback_query(OnboardingStates.allergies, F.data == "allergies_no")
async def allergies_no(callback: CallbackQuery, state: FSMContext):
    await state.update_data(allergies="Нет")
    await state.set_state(OnboardingStates.excluded_products)
    await callback.message.edit_text(
        "Есть продукты, которые хочешь исключить из рациона?\n\n"
        "Пример: сахар, фастфуд, майонез.\nЕсли нет — напиши: нет"
    )
    await callback.answer()


@router.message(OnboardingStates.excluded_products, F.text, ~F.text.startswith("/"))
async def excluded_products_step(message: Message, state: FSMContext):
    await state.update_data(excluded_products=message.text.strip())
    await state.set_state(OnboardingStates.restrictions)
    await message.answer(
        "Напиши, что ты не ешь или чего хочешь избегать.\n\n"
        "Пример: сахар, молочка, свинина, глютен.\n"
        "Если ограничений нет — напиши: нет"
    )


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
    await state.set_state(OnboardingStates.excluded_products)
    await message.answer(
        "Есть продукты, которые хочешь исключить из рациона?\n\n"
        "Пример: сахар, фастфуд, майонез.\nЕсли нет — напиши: нет"
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
