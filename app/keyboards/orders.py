from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import Dish


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


def order_categories_keyboard(
    categories: list[tuple[str, str]],
) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=title, callback_data=f"oc:{slug}")]
        for slug, title in categories
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def order_dishes_keyboard(
    dishes: list[Dish],
    cart: dict[int, int],
    category_slug: str,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for d in dishes:
        qty = cart.get(d.id, 0)
        label = f"{d.name}  [{qty}]" if qty > 0 else d.name
        rows.append([InlineKeyboardButton(text=label, callback_data="noop")])
        rows.append([
            InlineKeyboardButton(text="➖", callback_data=f"od-:{d.id}:{category_slug}"),
            InlineKeyboardButton(text=f"{qty} шт", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"od+:{d.id}:{category_slug}"),
        ])
    rows.append([
        InlineKeyboardButton(text="⬅ Категории", callback_data="oc:back"),
    ])
    total_items = sum(cart.values())
    if total_items > 0:
        rows.append([
            InlineKeyboardButton(
                text=f"✅ Готово ({total_items} шт)",
                callback_data="od:done",
            ),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _cart_summary(cart: dict[int, int]) -> str:
    total = sum(cart.values())
    return f"🛒 В корзине: {total} шт" if total > 0 else "🛒 Корзина пуста"
