from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    client_name = State()
    client_phone = State()
    items = State()
    address = State()
    delivery_time = State()
    confirm = State()
