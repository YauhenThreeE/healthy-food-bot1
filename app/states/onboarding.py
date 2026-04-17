from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    goal = State()
    sex = State()
    age = State()
    height_cm = State()
    weight_kg = State()
    activity_level = State()
    diet_type = State()
    allergies = State()
    excluded_products = State()
    restrictions = State()
    household_size = State()
    cooking_time = State()
    budget = State()
    equipment = State()
    confirm = State()
