from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def order_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить заказ",
                    callback_data="order_confirm_yes",
                ),
                InlineKeyboardButton(
                    text="🔁 Заполнить заново",
                    callback_data="order_confirm_restart",
                ),
            ]
        ]
    )
