from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.nutrition import add_conversation, get_recent_conversations


async def log_conversation_message(
    session: AsyncSession,
    user_id: int,
    role: str,
    message: str,
    intent: str | None = None,
) -> None:
    if not message:
        return
    await add_conversation(session, user_id, role=role, message=message[:4000], intent=intent)


async def build_recent_context(session: AsyncSession, user_id: int, limit: int = 10) -> str:
    rows = await get_recent_conversations(session, user_id, limit=limit)
    return "\n".join(f"{row.role}: {row.message}" for row in rows)
