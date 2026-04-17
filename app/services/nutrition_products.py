from __future__ import annotations

from app.db.models import Product
from app.repositories.nutrition import create_product, search_products


def nutrition_for_grams(product: Product, grams: float) -> dict[str, float]:
    k = max(0.0, grams) / 100.0
    micronutrients = dict(product.micronutrients_json or {})
    micronutrients_scaled = {
        key: round(float(value) * k, 3) for key, value in micronutrients.items()
    }
    return {
        "grams": round(grams, 2),
        "calories": round(product.calories_100g * k, 2),
        "protein": round(product.protein_100g * k, 2),
        "fat": round(product.fat_100g * k, 2),
        "carbs": round(product.carbs_100g * k, 2),
        "fiber": round(product.fiber_100g * k, 2),
        "sugar": round(product.sugar_100g * k, 2),
        "sodium_mg": round(product.sodium_mg_100g * k, 2),
        "water_ml": round(product.water_ml_100g * k, 2),
        "micronutrients_json": micronutrients_scaled,
    }


async def create_product_entry(session, payload: dict) -> Product:
    return await create_product(session, **payload)


async def search_product_entries(session, query: str, limit: int = 10) -> list[Product]:
    return await search_products(session, query, limit=limit)
