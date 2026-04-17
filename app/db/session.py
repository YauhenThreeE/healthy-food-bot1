from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"

load_dotenv(BASE_DIR / ".env")


def _default_sqlite_url() -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{DATA_DIR / 'healthy_food.db'}"


def get_database_url() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        return _default_sqlite_url()
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    if url.startswith("postgresql+asyncpg://"):
        url = _normalize_asyncpg_url(url)
    return url


def _normalize_asyncpg_url(url: str) -> str:
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    sslmode = query.pop("sslmode", "").lower()
    query.pop("channel_binding", None)
    if sslmode and sslmode not in {"disable", "allow", "prefer"}:
        query.setdefault("ssl", "require")
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query),
            parsed.fragment,
        )
    )


DATABASE_URL = get_database_url()

engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "").lower() in ("1", "true", "yes"),
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_safe_schema_updates(conn)


async def _apply_safe_schema_updates(conn) -> None:
    """
    Lightweight migration strategy for projects without Alembic.
    Creates new tables via create_all and applies additive columns for SQLite.
    """
    if not DATABASE_URL.startswith("sqlite+"):
        return

    sqlite_additions: dict[str, dict[str, str]] = {
        "users": {
            "last_name": "TEXT",
            "sex": "TEXT",
            "age": "INTEGER",
            "height_cm": "FLOAT",
            "weight_kg": "FLOAT",
            "target_weight_kg": "FLOAT",
            "activity_level": "TEXT",
            "goal": "TEXT",
            "diet_type": "TEXT",
            "allergies_json": "JSON",
            "excluded_products_json": "JSON",
            "health_flags_json": "JSON",
            "daily_calories_target": "FLOAT",
            "daily_protein_target": "FLOAT",
            "daily_fat_target": "FLOAT",
            "daily_carbs_target": "FLOAT",
            "daily_fiber_target": "FLOAT",
            "daily_water_target_ml": "FLOAT",
            "updated_at": "DATETIME",
        },
        "dishes": {
            "recipe_json": "JSON",
            "total_weight_g": "FLOAT",
            "calories_total": "FLOAT",
            "protein_total": "FLOAT",
            "fat_total": "FLOAT",
            "carbs_total": "FLOAT",
            "fiber_total": "FLOAT",
            "sugar_total": "FLOAT",
            "sodium_mg_total": "FLOAT",
            "water_ml_total": "FLOAT",
            "micronutrients_json": "JSON",
            "updated_at": "DATETIME",
        },
    }

    for table_name, columns in sqlite_additions.items():
        pragma = await conn.execute(text(f"PRAGMA table_info({table_name})"))
        existing = {row[1] for row in pragma.fetchall()}
        for column_name, sqlite_type in columns.items():
            if column_name in existing:
                continue
            await conn.execute(
                text(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sqlite_type}"
                )
            )
