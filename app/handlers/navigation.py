from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.states.onboarding import OnboardingStates
from app.states.orders import OrderStates
from app.keyboards.onboarding import goal_keyboard

router = Router()


@router.callback_query(F.data == "go:onboarding")
async def go_onboarding(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(OnboardingStates.goal)
    await callback.message.edit_text(
        "Давай настроим твой профиль питания.\n\n"
        "Какая у тебя главная цель?",
        reply_markup=goal_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "go:menu")
async def go_menu(callback: CallbackQuery, session: AsyncSession):
    from app.handlers.catalog import _fetch_categories, _categories_keyboard

    rows = await _fetch_categories(session)
    if not rows:
        await callback.answer("Меню пока пустое.", show_alert=True)
        return
    await callback.message.edit_text(
        "Выбери категорию — покажу блюда с кратким описанием.",
        reply_markup=_categories_keyboard(rows),
    )
    await callback.answer()


@router.callback_query(F.data == "go:order")
async def go_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(OrderStates.client_name)
    await callback.message.edit_text(
        "Давай оформим заказ еды для клиента.\n\nКак зовут клиента?"
    )
    await callback.answer()


@router.callback_query(F.data == "go:tip")
async def go_tip(callback: CallbackQuery):
    await callback.message.edit_text(
        "Напиши свой вопрос командой:\n"
        "<code>/tip Что съесть на завтрак?</code>\n\n"
        "Или просто <code>/tip</code> — получишь совет дня.",
        parse_mode="HTML",
    )
    await callback.answer()
