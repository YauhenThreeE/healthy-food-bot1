from __future__ import annotations

from dataclasses import dataclass

from app.services.food_database import normalize_product_name, supported_products


@dataclass(frozen=True)
class ParsedFoodItem:
    product_name: str
    grams: float
    confidence: float
    note: str


def parse_free_text_meal(raw_text: str) -> dict:
    text = normalize_product_name(raw_text)
    if not text:
        return {"items": [], "raw_input": raw_text, "note": "empty"}

    parts = [p.strip() for p in text.replace(" и ", ",").split(",") if p.strip()]
    known = supported_products()
    items: list[ParsedFoodItem] = []
    for part in parts:
        grams = 100.0
        tokens = part.split()
        for token in tokens:
            if token.endswith("г") and token[:-1].replace(".", "", 1).isdigit():
                grams = float(token[:-1])
            elif token.isdigit():
                grams = float(token) * 100.0
        product_guess = next((name for name in known if name in part), tokens[-1] if tokens else part)
        confidence = 0.88 if product_guess in known else 0.55
        items.append(
            ParsedFoodItem(
                product_name=product_guess,
                grams=grams,
                confidence=confidence,
                note="detected from free text",
            )
        )
    return {
        "items": [item.__dict__ for item in items],
        "raw_input": raw_text,
        "note": "heuristic_parser",
    }
