from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    goal = State()
    allergies = State()
    restrictions = State()
    household_size = State()
    cooking_time = State()
    budget = State()
    equipment = State()
    confirm = State()
