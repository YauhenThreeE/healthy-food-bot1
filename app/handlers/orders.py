from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Dish
from app.keyboards.orders import (
    order_categories_keyboard,
    order_confirm_keyboard,
    order_dishes_keyboard,
)
from app.states.orders import OrderStates

router = Router()


async def _fetch_categories(session: AsyncSession) -> list[tuple[str, str]]:
    stmt = (
        select(Dish.category_slug, Dish.category_title)
        .group_by(Dish.category_slug, Dish.category_title)
        .order_by(Dish.category_title)
    )
    return list((await session.execute(stmt)).all())


async def _fetch_dishes_by_slug(
    session: AsyncSession, slug: str
) -> list[Dish]:
    stmt = select(Dish).where(Dish.category_slug == slug).order_by(Dish.id)
    return list((await session.execute(stmt)).scalars())


def _format_cart(cart: dict[int, int], dish_names: dict[int, str]) -> str:
    if not cart:
        return "—"
    lines = []
    for dish_id, qty in cart.items():
        name = dish_names.get(dish_id, f"#{dish_id}")
        lines.append(f"{name} x{qty}")
    return ", ".join(lines)


def format_order(data: dict) -> str:
    cart: dict[int, int] = data.get("cart", {})
    dish_names: dict[int, str] = data.get("dish_names", {})
    items_text = _format_cart(cart, dish_names) if cart else data.get("items", "—")
    return (
        "🧾 Черновик заказа:\n\n"
        f"👤 Клиент: {data.get('client_name', '-')}\n"
        f"📞 Телефон: {data.get('client_phone', '-')}\n"
        f"🍱 Заказ: {items_text}\n"
        f"📍 Адрес: {data.get('address', '-')}\n"
        f"🕒 Время доставки: {data.get('delivery_time', '-')}\n"
    )


@router.message(Command("order"))
async def start_order(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(OrderStates.client_name)
    await message.answer("Давай оформим заказ еды для клиента.\n\nКак зовут клиента?")


@router.message(OrderStates.client_name, F.text, ~F.text.startswith("/"))
async def order_client_name(message: Message, state: FSMContext):
    await state.update_data(client_name=message.text.strip())
    await state.set_state(OrderStates.client_phone)
    await message.answer("Укажи телефон клиента для связи.")


@router.message(OrderStates.client_phone, F.text, ~F.text.startswith("/"))
async def order_client_phone(
    message: Message, state: FSMContext, session: AsyncSession
):
    await state.update_data(client_phone=message.text.strip(), cart={}, dish_names={})
    await state.set_state(OrderStates.choose_category)
    categories = await _fetch_categories(session)
    if not categories:
        await message.answer("Каталог пуст. Обратись к администратору.")
        await state.clear()
        return
    await message.answer(
        "🍽 Выбери категорию блюд:",
        reply_markup=order_categories_keyboard(categories),
    )


# --- Category selection ---

@router.callback_query(OrderStates.choose_category, F.data.startswith("oc:"))
async def on_order_category(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    slug = (callback.data or "").split(":", 1)[1]
    if slug == "back":
        categories = await _fetch_categories(session)
        await callback.message.edit_text(
            "🍽 Выбери категорию блюд:",
            reply_markup=order_categories_keyboard(categories),
        )
        await callback.answer()
        return
    dishes = await _fetch_dishes_by_slug(session, slug)
    if not dishes:
        await callback.answer("Пусто", show_alert=True)
        return

    data = await state.get_data()
    cart = data.get("cart", {})

    await state.set_state(OrderStates.choose_dishes)
    total = sum(cart.values())
    header = f"Выбери блюда (в корзине: {total} шт):" if total else "Выбери блюда:"
    await callback.message.edit_text(
        header,
        reply_markup=order_dishes_keyboard(dishes, cart, slug),
    )
    await callback.answer()


# --- Dish +/- buttons ---

@router.callback_query(OrderStates.choose_dishes, F.data.startswith("od+:"))
async def on_dish_add(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    parts = (callback.data or "").split(":")
    dish_id = int(parts[1])
    slug = parts[2]

    data = await state.get_data()
    cart: dict[int, int] = data.get("cart", {})
    dish_names: dict[int, str] = data.get("dish_names", {})

    cart[dish_id] = cart.get(dish_id, 0) + 1

    dish = await session.get(Dish, dish_id)
    if dish:
        dish_names[dish_id] = dish.name

    await state.update_data(cart=cart, dish_names=dish_names)

    dishes = await _fetch_dishes_by_slug(session, slug)
    total = sum(cart.values())
    await callback.message.edit_reply_markup(
        reply_markup=order_dishes_keyboard(dishes, cart, slug),
    )
    await callback.answer(f"Добавлено ({total} шт в корзине)")


@router.callback_query(OrderStates.choose_dishes, F.data.startswith("od-:"))
async def on_dish_remove(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    parts = (callback.data or "").split(":")
    dish_id = int(parts[1])
    slug = parts[2]

    data = await state.get_data()
    cart: dict[int, int] = data.get("cart", {})

    if cart.get(dish_id, 0) > 0:
        cart[dish_id] -= 1
        if cart[dish_id] == 0:
            cart.pop(dish_id)

    await state.update_data(cart=cart)

    dishes = await _fetch_dishes_by_slug(session, slug)
    total = sum(cart.values())
    await callback.message.edit_reply_markup(
        reply_markup=order_dishes_keyboard(dishes, cart, slug),
    )
    await callback.answer(f"Убрано ({total} шт в корзине)")


@router.callback_query(OrderStates.choose_dishes, F.data == "oc:back")
async def on_dishes_back_to_categories(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    await state.set_state(OrderStates.choose_category)
    categories = await _fetch_categories(session)
    data = await state.get_data()
    total = sum(data.get("cart", {}).values())
    header = f"🍽 Выбери категорию (в корзине: {total} шт):" if total else "🍽 Выбери категорию блюд:"
    await callback.message.edit_text(
        header,
        reply_markup=order_categories_keyboard(categories),
    )
    await callback.answer()


@router.callback_query(OrderStates.choose_dishes, F.data == "noop")
async def on_noop(callback: CallbackQuery):
    await callback.answer()


# --- Done selecting dishes ---

@router.callback_query(OrderStates.choose_dishes, F.data == "od:done")
async def on_dishes_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})
    if not cart or sum(cart.values()) == 0:
        await callback.answer("Корзина пуста — выбери хотя бы одно блюдо", show_alert=True)
        return

    dish_names = data.get("dish_names", {})
    summary = _format_cart(cart, dish_names)

    await state.set_state(OrderStates.address)
    await callback.message.edit_text(f"🛒 Выбрано: {summary}\n\nУкажи адрес доставки.")
    await callback.answer()


# --- Address & delivery time (unchanged flow) ---

@router.message(OrderStates.address, F.text, ~F.text.startswith("/"))
async def order_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text.strip())
    await state.set_state(OrderStates.delivery_time)
    await message.answer("На какое время нужна доставка?")


@router.message(OrderStates.delivery_time, F.text, ~F.text.startswith("/"))
async def order_delivery_time(message: Message, state: FSMContext):
    await state.update_data(delivery_time=message.text.strip())
    data = await state.get_data()

    await state.set_state(OrderStates.confirm)
    await message.answer(
        format_order(data) + "\nВсе верно?",
        reply_markup=order_confirm_keyboard(),
    )


@router.callback_query(OrderStates.confirm, F.data == "order_confirm_yes")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(
        "Заказ создан ✅\n\n"
        f"{format_order(data)}\n"
        "Мы передали заказ в обработку."
    )
    await state.clear()
    await callback.answer()


@router.callback_query(OrderStates.confirm, F.data == "order_confirm_restart")
async def restart_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(OrderStates.client_name)
    await callback.message.edit_text("Ок, заполним заново.\n\nКак зовут клиента?")
    await callback.answer()
