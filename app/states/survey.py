from aiogram.fsm.state import State, StatesGroup


class SurveyStates(StatesGroup):
    energy = State()
    meals_per_day = State()
    water = State()
    snacks = State()
    sleep = State()
    challenge = State()
    confirm = State()
