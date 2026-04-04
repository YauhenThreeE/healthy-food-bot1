from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def goal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Похудеть", callback_data="goal_lose_weight")],
            [InlineKeyboardButton(text="Поддерживать форму", callback_data="goal_maintain")],
            [InlineKeyboardButton(text="Набрать массу", callback_data="goal_gain")],
            [InlineKeyboardButton(text="Питаться чище", callback_data="goal_clean_eating")],
            [InlineKeyboardButton(text="Семейное питание", callback_data="goal_family")],
        ]
    )


def yes_no_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data=f"{prefix}_yes"),
                InlineKeyboardButton(text="Нет", callback_data=f"{prefix}_no"),
            ]
        ]
    )


def cooking_time_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="До 15 минут", callback_data="cooking_15")],
            [InlineKeyboardButton(text="До 30 минут", callback_data="cooking_30")],
            [InlineKeyboardButton(text="30–45 минут", callback_data="cooking_45")],
        ]
    )


def budget_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Эконом", callback_data="budget_low")],
            [InlineKeyboardButton(text="Средний", callback_data="budget_medium")],
            [InlineKeyboardButton(text="Выше среднего", callback_data="budget_high")],
        ]
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить", callback_data="confirm_yes")],
            [InlineKeyboardButton(text="Заполнить заново", callback_data="confirm_restart")],
        ]
    )
