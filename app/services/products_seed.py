from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.nutrition import seed_default_products

SEED_PRODUCTS = [
    {
        "name": "курица",
        "brand": None,
        "category": "protein",
        "calories_100g": 165,
        "protein_100g": 31,
        "fat_100g": 3.6,
        "carbs_100g": 0,
        "fiber_100g": 0,
        "sugar_100g": 0,
        "sodium_mg_100g": 74,
        "saturated_fat_100g": 1.0,
        "water_ml_100g": 65,
        "micronutrients_json": {"vitamin_a": 0.02, "vitamin_b": 0.18, "vitamin_c": 0.0, "vitamin_d": 0.0},
        "allergens_json": {},
        "is_verified": True,
    },
    {
        "name": "рис",
        "brand": None,
        "category": "grain",
        "calories_100g": 130,
        "protein_100g": 2.7,
        "fat_100g": 0.3,
        "carbs_100g": 28,
        "fiber_100g": 0.4,
        "sugar_100g": 0.1,
        "sodium_mg_100g": 1,
        "saturated_fat_100g": 0.1,
        "water_ml_100g": 68,
        "micronutrients_json": {"vitamin_a": 0.0, "vitamin_b": 0.04, "vitamin_c": 0.0, "vitamin_d": 0.0},
        "allergens_json": {},
        "is_verified": True,
    },
    {
        "name": "яйца",
        "brand": None,
        "category": "protein",
        "calories_100g": 155,
        "protein_100g": 13,
        "fat_100g": 11,
        "carbs_100g": 1.1,
        "fiber_100g": 0,
        "sugar_100g": 1.1,
        "sodium_mg_100g": 124,
        "saturated_fat_100g": 3.3,
        "water_ml_100g": 76,
        "micronutrients_json": {"vitamin_a": 0.16, "vitamin_b": 0.25, "vitamin_c": 0.0, "vitamin_d": 2.0},
        "allergens_json": {"eggs": True},
        "is_verified": True,
    },
    {
        "name": "яблоко",
        "brand": None,
        "category": "fruit",
        "calories_100g": 52,
        "protein_100g": 0.3,
        "fat_100g": 0.2,
        "carbs_100g": 14,
        "fiber_100g": 2.4,
        "sugar_100g": 10.4,
        "sodium_mg_100g": 1,
        "saturated_fat_100g": 0.0,
        "water_ml_100g": 86,
        "micronutrients_json": {"vitamin_a": 0.003, "vitamin_b": 0.02, "vitamin_c": 4.6, "vitamin_d": 0.0},
        "allergens_json": {},
        "is_verified": True,
    },
]


async def seed_products_if_empty(session: AsyncSession) -> int:
    return await seed_default_products(session, SEED_PRODUCTS)
