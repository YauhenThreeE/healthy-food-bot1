from __future__ import annotations

import math

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Dish

router = Router()

PAGE_SIZE = 6


def _categories_keyboard(rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=title, callback_data=f"m:{slug}:0")]
        for slug, title in rows
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _dish_label(name: str) -> str:
    name = name.strip()
    if len(name) <= 40:
        return name
    return name[:37] + "…"


def _dish_page_keyboard(
    slug: str,
    page: int,
    total_pages: int,
    dishes_on_page: list[Dish],
) -> InlineKeyboardMarkup:
    grid: list[list[InlineKeyboardButton]] = []
    for d in dishes_on_page:
        grid.append(
            [InlineKeyboardButton(text=_dish_label(d.name), callback_data=f"d:{d.id}")]
        )
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"m:{slug}:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"m:{slug}:{page + 1}"))
    if nav:
        grid.append(nav)
    grid.append([InlineKeyboardButton(text="⬅ К категориям", callback_data="m:home:0")])
    return InlineKeyboardMarkup(inline_keyboard=grid)


async def _fetch_categories(session: AsyncSession) -> list[tuple[str, str]]:
    stmt = (
        select(Dish.category_slug, Dish.category_title)
        .group_by(Dish.category_slug, Dish.category_title)
        .order_by(Dish.category_title)
    )
    result = await session.execute(stmt)
    return list(result.all())


@router.message(F.text == "/menu")
async def cmd_menu(message: Message, session: AsyncSession):
    rows = await _fetch_categories(session)
    if not rows:
        await message.answer("Меню пока пустое. Администратор ещё не загрузил блюда.")
        return
    await message.answer(
        "Выбери категорию — покажу блюда с кратким описанием.",
        reply_markup=_categories_keyboard(rows),
    )


@router.callback_query(F.data.regexp(r"^m:([^:]+):(\d+)$"))
async def on_menu_nav(callback: CallbackQuery, session: AsyncSession):
    parts = (callback.data or "").split(":")
    slug = parts[1]
    page = int(parts[2])

    if slug == "home":
        rows = await _fetch_categories(session)
        if not rows:
            await callback.answer("Нет категорий", show_alert=True)
            return
        await callback.message.edit_text(
            "Выбери категорию — покажу блюда с кратким описанием.",
            reply_markup=_categories_keyboard(rows),
        )
        await callback.answer()
        return

    count_stmt = select(func.count()).select_from(Dish).where(Dish.category_slug == slug)
    total = await session.scalar(count_stmt)
    total = int(total or 0)
    if total == 0:
        await callback.answer("В этой категории пока пусто", show_alert=True)
        return

    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    offset = page * PAGE_SIZE

    stmt = (
        select(Dish)
        .where(Dish.category_slug == slug)
        .order_by(Dish.id)
        .offset(offset)
        .limit(PAGE_SIZE)
    )
    dishes = list((await session.execute(stmt)).scalars())

    title = dishes[0].category_title if dishes else "Блюда"
    lines = [f"🍽 {title} — стр. {page + 1}/{total_pages}\n"]
    for d in dishes:
        meta = []
        if d.prep_minutes is not None:
            meta.append(f"{d.prep_minutes} мин")
        if d.calories is not None:
            meta.append(f"~{d.calories} ккал")
        suffix = f" ({', '.join(meta)})" if meta else ""
        lines.append(f"• <b>{d.name}</b>{suffix}\n  {d.description[:180]}{'…' if len(d.description) > 180 else ''}")

    kb = _dish_page_keyboard(slug, page, total_pages, dishes)
    await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.regexp(r"^d:(\d+)$"))
async def on_dish_detail(callback: CallbackQuery, session: AsyncSession):
    did = int((callback.data or "").split(":")[1])
    dish = await session.get(Dish, did)
    if not dish:
        await callback.answer("Блюдо не найдено", show_alert=True)
        return
    tags = dish.tags or []
    tags_line = ", ".join(tags) if tags else "—"
    meta = []
    if dish.prep_minutes is not None:
        meta.append(f"⏱ ~{dish.prep_minutes} мин")
    if dish.calories is not None:
        meta.append(f"🔥 ~{dish.calories} ккал")
    head = " ".join(meta)
    text = (
        f"<b>{dish.name}</b>\n"
        f"{dish.category_title} · {head}\n\n"
        f"{dish.description}\n\n"
        f"Теги: {tags_line}"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅ В список", callback_data=f"m:{dish.category_slug}:0")],
            [InlineKeyboardButton(text="⬅ К категориям", callback_data="m:home:0")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()
