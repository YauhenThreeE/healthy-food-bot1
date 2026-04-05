from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Dish

SEED_DISHES: list[dict] = [
    {
        "name": "Овсянка с ягодами и йогуртом",
        "description": "Овсяные хлопья на воде или молоке, свежие или замороженные ягоды, греческий йогурт.",
        "category_slug": "breakfast",
        "category_title": "Завтраки",
        "prep_minutes": 15,
        "calories": 320,
        "tags": ["клетчатка", "без жарки"],
    },
    {
        "name": "Омлет с овощами",
        "description": "Яйца, перец, томаты, шпинат. На сковороде с каплей масла или в духовке.",
        "category_slug": "breakfast",
        "category_title": "Завтраки",
        "prep_minutes": 20,
        "calories": 280,
        "tags": ["белок", "овощи"],
    },
    {
        "name": "Тост с авокадо и яйцом пашот",
        "description": "Цельнозерновой хлеб, авокадо, яйцо пашот, лимон, соль/перец.",
        "category_slug": "breakfast",
        "category_title": "Завтраки",
        "prep_minutes": 25,
        "calories": 380,
        "tags": ["полезные жиры"],
    },
    {
        "name": "Смузи-боул",
        "description": "Банан, шпинат, молоко/растительное, сверху гранола и семена.",
        "category_slug": "breakfast",
        "category_title": "Завтраки",
        "prep_minutes": 10,
        "calories": 350,
        "tags": ["быстро"],
    },
    {
        "name": "Куриная грудка с киноа и салатом",
        "description": "Запечённая грудка, киноа, микс салата, оливковое масло и лимон.",
        "category_slug": "lunch",
        "category_title": "Обеды",
        "prep_minutes": 35,
        "calories": 480,
        "tags": ["белок", "киноа"],
    },
    {
        "name": "Греческий салат с нутом",
        "description": "Огурцы, томаты, фета, оливки, нут, оливковое масло.",
        "category_slug": "lunch",
        "category_title": "Обеды",
        "prep_minutes": 15,
        "calories": 420,
        "tags": ["вегетарианское"],
    },
    {
        "name": "Рыбные котлеты с гречкой",
        "description": "Котлеты из минтая/трески на пару или в духовке, гречка, овощной гарнир.",
        "category_slug": "lunch",
        "category_title": "Обеды",
        "prep_minutes": 40,
        "calories": 450,
        "tags": ["рыба"],
    },
    {
        "name": "Боул с лососем и рисом",
        "description": "Рис бурый/басмати, лосось запечённый, авокадо, огурец, соус на йогурте.",
        "category_slug": "lunch",
        "category_title": "Обеды",
        "prep_minutes": 30,
        "calories": 520,
        "tags": ["омега-3"],
    },
    {
        "name": "Индейка с овощами на сковороде",
        "description": "Филе индейки, брокколи, морковь, соевый соус в малых количествах.",
        "category_slug": "dinner",
        "category_title": "Ужины",
        "prep_minutes": 30,
        "calories": 400,
        "tags": ["низкокалорийно"],
    },
    {
        "name": "Запечённые овощи с тофу",
        "description": "Кабачок, перец, баклажан, тофу, специи, духовка.",
        "category_slug": "dinner",
        "category_title": "Ужины",
        "prep_minutes": 35,
        "calories": 320,
        "tags": ["веган"],
    },
    {
        "name": "Треска с картофелем и спаржей",
        "description": "Запечённая треска, молодой картофель, спаржа, лимон.",
        "category_slug": "dinner",
        "category_title": "Ужины",
        "prep_minutes": 40,
        "calories": 430,
        "tags": ["рыба"],
    },
    {
        "name": "Суп с чечевицей и шпинатом",
        "description": "Чечевица, морковь, лук, шпинат, немного куркумы.",
        "category_slug": "dinner",
        "category_title": "Ужины",
        "prep_minutes": 35,
        "calories": 300,
        "tags": ["согревающее"],
    },
    {
        "name": "Яблоко с арахисовой пастой",
        "description": "Дольки яблока + 1 ст.л. пасты без сахара.",
        "category_slug": "snack",
        "category_title": "Перекусы",
        "prep_minutes": 5,
        "calories": 200,
        "tags": ["быстро"],
    },
    {
        "name": "Творог с орехами",
        "description": "Нежирный творог, горсть грецких орехов, корица.",
        "category_slug": "snack",
        "category_title": "Перекусы",
        "prep_minutes": 5,
        "calories": 220,
        "tags": ["белок"],
    },
    {
        "name": "Хумус с овощными палочками",
        "description": "Хумус + морковь/сельдерей/перец соломкой.",
        "category_slug": "snack",
        "category_title": "Перекусы",
        "prep_minutes": 10,
        "calories": 180,
        "tags": ["клетчатка"],
    },
]


async def seed_dishes_if_empty(session: AsyncSession) -> int:
    count = await session.scalar(select(func.count()).select_from(Dish))
    if count and count > 0:
        return 0
    for row in SEED_DISHES:
        session.add(Dish(**row))
    await session.flush()
    return len(SEED_DISHES)
