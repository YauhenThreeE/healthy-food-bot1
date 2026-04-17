from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def after_start_keyboard(show_profile: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if not show_profile:
        rows.append([InlineKeyboardButton(
            text="📝 Заполнить профиль",
            callback_data="go:onboarding",
        )])
    else:
        rows.append([InlineKeyboardButton(
            text="👤 Мой профиль",
            callback_data="go:profile",
        )])
    rows.append([InlineKeyboardButton(
        text="🍽 Меню блюд",
        callback_data="go:menu",
    )])
    rows.append([InlineKeyboardButton(
        text="🛒 Оформить заказ",
        callback_data="go:order",
    )])
    rows.append([InlineKeyboardButton(
        text="💡 Совет по питанию",
        callback_data="go:tip",
    )])
    rows.append([InlineKeyboardButton(
        text="📝 Записать приём пищи",
        callback_data="go:log_food",
    )])
    rows.append([InlineKeyboardButton(
        text="📊 Итог за сегодня",
        callback_data="go:today",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)
