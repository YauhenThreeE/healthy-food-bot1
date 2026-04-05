from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.keyboards.orders import order_confirm_keyboard
from app.states.orders import OrderStates

router = Router()


def format_order(data: dict) -> str:
    return (
        "🧾 Черновик заказа:\n\n"
        f"👤 Клиент: {data.get('client_name', '-')}\n"
        f"📞 Телефон: {data.get('client_phone', '-')}\n"
        f"🍱 Заказ: {data.get('items', '-')}\n"
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
async def order_client_phone(message: Message, state: FSMContext):
    await state.update_data(client_phone=message.text.strip())
    await state.set_state(OrderStates.items)
    await message.answer(
        "Что нужно заказать?\n"
        "Напиши блюда и количество одним сообщением.\n\n"
        "Пример: боул с курицей x2, салат греческий x1"
    )


@router.message(OrderStates.items, F.text, ~F.text.startswith("/"))
async def order_items(message: Message, state: FSMContext):
    await state.update_data(items=message.text.strip())
    await state.set_state(OrderStates.address)
    await message.answer("Укажи адрес доставки.")


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
