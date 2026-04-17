from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.nutrition import get_ai_memory, save_ai_memory


async def remember_fact(
    session: AsyncSession,
    user_id: int,
    memory_key: str,
    memory_value: str,
    memory_type: str = "preference",
    importance: float = 0.6,
):
    return await save_ai_memory(
        session=session,
        user_id=user_id,
        memory_type=memory_type,
        memory_key=memory_key,
        memory_value=memory_value,
        importance=importance,
    )


async def load_memory_context(session: AsyncSession, user_id: int, limit: int = 10) -> list[dict]:
    rows = await get_ai_memory(session, user_id, limit=limit)
    return [
        {
            "type": row.memory_type,
            "key": row.memory_key,
            "value": row.memory_value,
            "importance": row.importance,
        }
        for row in rows
    ]
