from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def survey_energy_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Энергии хватает", callback_data="survey:energy:good")],
            [InlineKeyboardButton(text="После обеда просадка", callback_data="survey:energy:afternoon_drop")],
            [InlineKeyboardButton(text="Часто чувствую усталость", callback_data="survey:energy:tired")],
        ]
    )


def survey_meals_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1-2 раза", callback_data="survey:meals:1_2")],
            [InlineKeyboardButton(text="3 раза", callback_data="survey:meals:3")],
            [InlineKeyboardButton(text="4+ раза", callback_data="survey:meals:4_plus")],
            [InlineKeyboardButton(text="Нерегулярно", callback_data="survey:meals:irregular")],
        ]
    )


def survey_water_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Меньше 1 литра", callback_data="survey:water:low")],
            [InlineKeyboardButton(text="1-2 литра", callback_data="survey:water:medium")],
            [InlineKeyboardButton(text="Больше 2 литров", callback_data="survey:water:high")],
        ]
    )


def survey_snacks_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Редко перекусываю", callback_data="survey:snacks:rare")],
            [InlineKeyboardButton(text="Сладкое / выпечка", callback_data="survey:snacks:sweet")],
            [InlineKeyboardButton(text="Соленое / фастфуд", callback_data="survey:snacks:salty")],
            [InlineKeyboardButton(text="Чаще вечером", callback_data="survey:snacks:evening")],
        ]
    )


def survey_sleep_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Меньше 6 часов", callback_data="survey:sleep:under_6")],
            [InlineKeyboardButton(text="6-7 часов", callback_data="survey:sleep:6_7")],
            [InlineKeyboardButton(text="7-8 часов", callback_data="survey:sleep:7_8")],
            [InlineKeyboardButton(text="Больше 8 часов", callback_data="survey:sleep:over_8")],
        ]
    )


def survey_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сохранить", callback_data="survey:confirm:save")],
            [InlineKeyboardButton(text="Пройти заново", callback_data="survey:confirm:restart")],
        ]
    )
