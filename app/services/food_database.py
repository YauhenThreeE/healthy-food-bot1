from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductNutrients:
    name: str
    calories: float
    protein: float
    fat: float
    carbs: float
    fiber: float
    sugar: float
    sodium_mg: float
    water_ml: float
    vitamins: dict[str, float]


def normalize_product_name(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


_BASE_PRODUCTS: dict[str, ProductNutrients] = {
    "курица": ProductNutrients("курица", 165, 31, 3.6, 0, 0, 0, 74, 65, {"A": 0.02, "B": 0.18, "C": 0.0, "D": 0.0}),
    "рис": ProductNutrients("рис", 130, 2.7, 0.3, 28, 0.4, 0.1, 1, 68, {"A": 0.0, "B": 0.04, "C": 0.0, "D": 0.0}),
    "яйца": ProductNutrients("яйца", 155, 13, 11, 1.1, 0, 1.1, 124, 76, {"A": 0.16, "B": 0.25, "C": 0.0, "D": 2.0}),
    "яблоко": ProductNutrients("яблоко", 52, 0.3, 0.2, 14, 2.4, 10.4, 1, 86, {"A": 0.003, "B": 0.02, "C": 4.6, "D": 0.0}),
    "банан": ProductNutrients("банан", 89, 1.1, 0.3, 23, 2.6, 12.2, 1, 75, {"A": 0.003, "B": 0.06, "C": 8.7, "D": 0.0}),
    "овсянка": ProductNutrients("овсянка", 379, 13.2, 6.5, 67.7, 10.1, 1.0, 2, 8, {"A": 0.0, "B": 0.12, "C": 0.0, "D": 0.0}),
    "молоко": ProductNutrients("молоко", 52, 3.4, 2.0, 4.8, 0.0, 5.2, 44, 89, {"A": 0.05, "B": 0.18, "C": 0.0, "D": 0.1}),
    "картофель": ProductNutrients("картофель", 77, 2.0, 0.1, 17, 2.2, 0.8, 6, 79, {"A": 0.0, "B": 0.08, "C": 19.7, "D": 0.0}),
    "гречка": ProductNutrients("гречка", 343, 13.3, 3.4, 71.5, 10.0, 0.0, 1, 10, {"A": 0.0, "B": 0.16, "C": 0.0, "D": 0.0}),
    "творог": ProductNutrients("творог", 121, 17.0, 5.0, 3.0, 0.0, 3.0, 41, 73, {"A": 0.03, "B": 0.20, "C": 0.0, "D": 0.0}),
}

_ALIASES = {
    "банана": "банан",
    "бананов": "банан",
    "гречки": "гречка",
    "картофеля": "картофель",
    "куриная грудка": "курица",
    "куриное филе": "курица",
    "курицы": "курица",
    "молока": "молоко",
    "яйцо": "яйца",
    "яйца куриные": "яйца",
    "яблока": "яблоко",
    "яблок": "яблоко",
    "овсяные хлопья": "овсянка",
    "овсянки": "овсянка",
    "риса": "рис",
    "творога": "творог",
}


def canonical_product_name(product_name: str) -> str:
    key = normalize_product_name(product_name)
    return _ALIASES.get(key, key)


def supported_products() -> list[str]:
    return sorted(_BASE_PRODUCTS.keys())


def lookup_product(product_name: str) -> ProductNutrients | None:
    return _BASE_PRODUCTS.get(canonical_product_name(product_name))
