from __future__ import annotations

from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AIMemory, Conversation, DailySummary, Dish, MealLog, Product, User


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return (
        await session.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one_or_none()


async def search_products(session: AsyncSession, query: str, limit: int = 10) -> list[Product]:
    pattern = f"%{query.strip().lower()}%"
    stmt = (
        select(Product)
        .where(func.lower(Product.name).like(pattern))
        .order_by(Product.is_verified.desc(), Product.name.asc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars())


async def find_products_mentioned_in_text(
    session: AsyncSession,
    text: str,
    limit: int = 5,
) -> list[Product]:
    normalized_text = f" {text.strip().lower()} "
    if not normalized_text.strip():
        return []

    products = list((await session.execute(select(Product))).scalars())
    matches = [
        product
        for product in products
        if len(product.name.strip()) >= 3
        and f" {product.name.strip().lower()} " in normalized_text
    ]
    matches.sort(key=lambda product: (-len(product.name), not product.is_verified, product.name))
    return matches[:limit]


async def get_product_by_name(session: AsyncSession, name: str) -> Product | None:
    stmt = select(Product).where(func.lower(Product.name) == name.strip().lower())
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_product(session: AsyncSession, **kwargs) -> Product:
    product = Product(**kwargs)
    session.add(product)
    await session.flush()
    return product


async def create_meal_log(session: AsyncSession, **kwargs) -> MealLog:
    log = MealLog(**kwargs)
    session.add(log)
    await session.flush()
    return log


async def get_daily_meal_logs(session: AsyncSession, user_id: int, day: date) -> list[MealLog]:
    stmt = (
        select(MealLog)
        .where(MealLog.user_id == user_id, MealLog.date == day)
        .order_by(MealLog.created_at.asc())
    )
    return list((await session.execute(stmt)).scalars())


async def upsert_daily_summary(session: AsyncSession, user_id: int, day: date, values: dict) -> DailySummary:
    existing = (
        await session.execute(
            select(DailySummary).where(DailySummary.user_id == user_id, DailySummary.date == day)
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = DailySummary(user_id=user_id, date=day, **values)
        session.add(existing)
    else:
        for key, value in values.items():
            setattr(existing, key, value)
    await session.flush()
    return existing


async def save_ai_memory(
    session: AsyncSession,
    user_id: int,
    memory_type: str,
    memory_key: str,
    memory_value: str,
    importance: float = 0.5,
) -> AIMemory:
    stmt = select(AIMemory).where(
        AIMemory.user_id == user_id,
        AIMemory.memory_type == memory_type,
        AIMemory.memory_key == memory_key,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is None:
        existing = AIMemory(
            user_id=user_id,
            memory_type=memory_type,
            memory_key=memory_key,
            memory_value=memory_value,
            importance=importance,
        )
        session.add(existing)
    else:
        existing.memory_value = memory_value
        existing.importance = importance
    await session.flush()
    return existing


async def get_ai_memory(session: AsyncSession, user_id: int, limit: int = 15) -> list[AIMemory]:
    stmt = (
        select(AIMemory)
        .where(AIMemory.user_id == user_id)
        .order_by(AIMemory.importance.desc(), AIMemory.updated_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars())


async def add_conversation(session: AsyncSession, user_id: int, role: str, message: str, intent: str | None = None) -> Conversation:
    row = Conversation(user_id=user_id, role=role, message=message, intent=intent)
    session.add(row)
    await session.flush()
    return row


async def get_recent_conversations(session: AsyncSession, user_id: int, limit: int = 12) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
    )
    return list(reversed(list((await session.execute(stmt)).scalars())))


async def seed_default_products(session: AsyncSession, rows: list[dict]) -> int:
    existing_count = await session.scalar(select(func.count()).select_from(Product))
    if existing_count and existing_count > 0:
        return 0
    for row in rows:
        session.add(Product(**row))
    await session.flush()
    return len(rows)
