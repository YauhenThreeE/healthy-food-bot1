from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import FSInputFile, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_admin_id
from app.db.models import Conversation, DailySummary, MealLog, ParticipantProfile, Product, Questionnaire, User
from app.services.participant_profiles import (
    add_participant_note,
    backfill_participant_profiles,
    export_participants_csv,
    get_participant_card_text,
    get_participant_notes_text,
    sync_participant_profile_by_questionnaire_id,
)

router = Router()


def _admin_id() -> int | None:
    return get_admin_id()


def _is_admin(message: Message) -> bool:
    admin_id = _admin_id()
    return bool(admin_id and message.from_user and message.from_user.id == admin_id)


async def _reject_non_admin(message: Message) -> bool:
    if _is_admin(message):
        return False
    await message.answer("Команда доступна только администратору.")
    return True


def _fmt_dt(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else "-"


def _display_user(user: User) -> str:
    username = f"@{user.username}" if user.username else "без username"
    name = " ".join(part for part in [user.first_name, user.last_name] if part) or "без имени"
    return f"{name} ({username}), id={user.telegram_id}"


@router.message(Command("admin_report"))
async def cmd_admin_report(message: Message, session: AsyncSession):
    if await _reject_non_admin(message):
        return

    today = date.today()
    week_ago = today - timedelta(days=7)
    total_users = await session.scalar(select(func.count()).select_from(User)) or 0
    users_with_profile = (
        await session.scalar(select(func.count()).select_from(User).where(User.goal.is_not(None), User.goal != ""))
        or 0
    )
    meals_today = (
        await session.scalar(select(func.count()).select_from(MealLog).where(MealLog.date == today))
        or 0
    )
    meals_week = (
        await session.scalar(select(func.count()).select_from(MealLog).where(MealLog.date >= week_ago))
        or 0
    )
    food_days_total = (
        await session.scalar(select(func.count(func.distinct(MealLog.date))).select_from(MealLog))
        or 0
    )
    ai_products = (
        await session.scalar(select(func.count()).select_from(Product).where(Product.is_verified.is_(False)))
        or 0
    )
    conversations_week = (
        await session.scalar(
            select(func.count()).select_from(Conversation).where(func.date(Conversation.created_at) >= week_ago)
        )
        or 0
    )

    await message.answer(
        "Админ-отчёт:\n"
        f"Пользователей всего: {total_users}\n"
        f"С заполненной целью: {users_with_profile}\n"
        f"Записей еды сегодня: {meals_today}\n"
        f"Записей еды за 7 дней: {meals_week}\n"
        f"Дней с записями еды: {food_days_total}\n"
        f"AI-продуктов в базе: {ai_products}\n"
        f"Сообщений/событий за 7 дней: {conversations_week}\n\n"
        "Команды:\n"
        "/admin_users\n"
        "/admin_user <telegram_id>\n"
        "/admin_food <telegram_id> [days]\n"
        "/admin_questionnaires\n"
        "/admin_participant <telegram_id>\n"
        "/admin_note <telegram_id> <текст>\n"
        "/admin_notes <telegram_id>\n"
        "/admin_sync_profiles\n"
        "/admin_export_participants"
    )


@router.message(Command("admin_users"))
async def cmd_admin_users(message: Message, session: AsyncSession):
    if await _reject_non_admin(message):
        return

    result = await session.execute(
        select(User)
        .options(selectinload(User.profile))
        .order_by(User.created_at.desc())
        .limit(20)
    )
    users = list(result.scalars())
    if not users:
        await message.answer("Пользователей пока нет.")
        return

    lines = ["Последние пользователи:"]
    for user in users:
        meal_count = (
            await session.scalar(select(func.count()).select_from(MealLog).where(MealLog.user_id == user.id))
            or 0
        )
        food_days = (
            await session.scalar(
                select(func.count(func.distinct(MealLog.date)))
                .select_from(MealLog)
                .where(MealLog.user_id == user.id)
            )
            or 0
        )
        lines.append(
            f"• {_display_user(user)}\n"
            f"  создан: {_fmt_dt(user.created_at)}, цель: {user.goal or '-'}, "
            f"еда: {meal_count}, дней: {food_days}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("admin_user"))
async def cmd_admin_user(message: Message, command: CommandObject, session: AsyncSession):
    if await _reject_non_admin(message):
        return

    raw_id = (command.args or "").strip()
    if not raw_id.isdigit():
        await message.answer("Формат: /admin_user <telegram_id>")
        return

    result = await session.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.telegram_id == int(raw_id))
    )
    user = result.scalar_one_or_none()
    if not user:
        await message.answer("Пользователь не найден.")
        return

    meal_count = await session.scalar(select(func.count()).select_from(MealLog).where(MealLog.user_id == user.id)) or 0
    food_days = (
        await session.scalar(
            select(func.count(func.distinct(MealLog.date)))
            .select_from(MealLog)
            .where(MealLog.user_id == user.id)
        )
        or 0
    )
    first_food_day = (
        await session.scalar(select(func.min(MealLog.date)).where(MealLog.user_id == user.id))
    )
    last_food_day = (
        await session.scalar(select(func.max(MealLog.date)).where(MealLog.user_id == user.id))
    )
    last_meal = (
        await session.execute(
            select(MealLog)
            .where(MealLog.user_id == user.id)
            .order_by(MealLog.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    last_conversation = (
        await session.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    await message.answer(
        "Пользователь:\n"
        f"{_display_user(user)}\n"
        f"Создан: {_fmt_dt(user.created_at)}\n"
        f"Обновлён: {_fmt_dt(user.updated_at)}\n"
        f"Цель: {user.goal or '-'}\n"
        f"Пол/возраст: {user.sex or '-'} / {user.age or '-'}\n"
        f"Рост/вес: {user.height_cm or '-'} см / {user.weight_kg or '-'} кг\n"
        f"Тип питания: {user.diet_type or '-'}\n"
        f"Цель ккал: {user.daily_calories_target or '-'}\n"
        f"Записей еды: {meal_count}\n"
        f"Дней записывал еду: {food_days}\n"
        f"Период еды: {first_food_day or '-'} — {last_food_day or '-'}\n"
        f"Последняя еда: {(last_meal.custom_name if last_meal else '-')}\n"
        f"Последнее событие: {(last_conversation.intent if last_conversation else '-')}"
    )


@router.message(Command("admin_food"))
async def cmd_admin_food(message: Message, command: CommandObject, session: AsyncSession):
    if await _reject_non_admin(message):
        return

    args = (command.args or "").split()
    raw_id = args[0] if args else ""
    if not raw_id.isdigit():
        await message.answer("Формат: /admin_food <telegram_id> [days]\nПример: /admin_food 123456789 7")
        return
    days = 7
    if len(args) > 1 and args[1].isdigit():
        days = min(max(int(args[1]), 1), 60)

    user = (
        await session.execute(select(User).where(User.telegram_id == int(raw_id)))
    ).scalar_one_or_none()
    if not user:
        await message.answer("Пользователь не найден.")
        return

    since = date.today() - timedelta(days=days - 1)
    logs = list(
        (
            await session.execute(
                select(MealLog)
                .where(MealLog.user_id == user.id, MealLog.date >= since)
                .order_by(MealLog.created_at.desc())
                .limit(60)
            )
        ).scalars()
    )
    if not logs:
        await message.answer("У пользователя пока нет записей еды.")
        return

    summary = (
        await session.execute(
            select(DailySummary)
            .where(DailySummary.user_id == user.id)
            .order_by(DailySummary.date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    food_days = (
        await session.scalar(
            select(func.count(func.distinct(MealLog.date)))
            .select_from(MealLog)
            .where(MealLog.user_id == user.id)
        )
        or 0
    )
    lines = [f"Питание: {_display_user(user)}"]
    lines.append(f"Всего дней с едой: {food_days}; показан период: {days} дн.")
    if summary:
        lines.append(
            f"Последний итог {summary.date}: "
            f"{summary.calories_fact:.0f}/{summary.calories_target:.0f} ккал"
        )
    lines.append("Последние записи:")
    for row in logs:
        lines.append(
            f"• {row.date} {row.custom_name or '-'} — "
            f"{row.grams:.0f} г, {row.calories:.0f} ккал, source={row.source}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("admin_questionnaires"))
async def cmd_admin_questionnaires(message: Message, session: AsyncSession):
    if await _reject_non_admin(message):
        return

    result = await session.execute(
        select(Questionnaire)
        .order_by(Questionnaire.created_at.desc(), Questionnaire.id.desc())
        .limit(20)
    )
    questionnaires = list(result.scalars())
    if not questionnaires:
        await message.answer("Анкет пока нет.")
        return

    lines = ["Последние анкеты:"]
    for questionnaire in questionnaires:
        profile_exists = await session.scalar(
            select(func.count())
            .select_from(ParticipantProfile)
            .where(ParticipantProfile.telegram_user_id == questionnaire.telegram_user_id)
        )
        username = f"@{questionnaire.username}" if questionnaire.username else "без username"
        lines.append(
            f"• id={questionnaire.id}, tg={questionnaire.telegram_user_id}, {username}\n"
            f"  статус: {questionnaire.status}, шаг: {questionnaire.current_question_index}, "
            f"профиль: {'да' if profile_exists else 'нет'}, создана: {_fmt_dt(questionnaire.created_at)}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("admin_participant"))
async def cmd_admin_participant(message: Message, command: CommandObject, session: AsyncSession):
    if await _reject_non_admin(message):
        return

    raw_id = (command.args or "").strip()
    if not raw_id.isdigit():
        await message.answer("Формат: /admin_participant <telegram_id>")
        return

    reference_id = int(raw_id)
    card = await get_participant_card_text(session, reference_id)
    if "Карточка участника не найдена" in card:
        questionnaire = await session.get(Questionnaire, reference_id)
        if questionnaire is not None:
            await sync_participant_profile_by_questionnaire_id(session, questionnaire.id)
            card = await get_participant_card_text(session, questionnaire.telegram_user_id)
    await message.answer(card[:4000])


@router.message(Command("admin_note"))
async def cmd_admin_note(message: Message, command: CommandObject, session: AsyncSession):
    if await _reject_non_admin(message):
        return

    args = (command.args or "").strip()
    if not args:
        await message.answer("Формат: /admin_note <telegram_id> <текст>")
        return

    telegram_id_text, _, note_text = args.partition(" ")
    if not telegram_id_text.isdigit() or not note_text.strip():
        await message.answer("Формат: /admin_note <telegram_id> <текст>")
        return

    note = await add_participant_note(
        session,
        telegram_user_id=int(telegram_id_text),
        note_text=note_text,
        author_telegram_id=message.from_user.id if message.from_user else None,
    )
    if note is None:
        await message.answer("Не удалось добавить заметку. Сначала нужна завершённая анкета участника.")
        return

    await message.answer("Заметка сохранена.")


@router.message(Command("admin_notes"))
async def cmd_admin_notes(message: Message, command: CommandObject, session: AsyncSession):
    if await _reject_non_admin(message):
        return

    raw_id = (command.args or "").strip()
    if not raw_id.isdigit():
        await message.answer("Формат: /admin_notes <telegram_id>")
        return

    text = await get_participant_notes_text(session, int(raw_id))
    await message.answer(text[:4000])


@router.message(Command("admin_export_participants"))
async def cmd_admin_export_participants(message: Message, session: AsyncSession):
    if await _reject_non_admin(message):
        return

    path = await export_participants_csv(session)
    if path is None:
        synced = await backfill_participant_profiles(session)
        path = await export_participants_csv(session)
        if path is None:
            await message.answer("Экспорт пустой: нет карточек участников.")
            return
        await message.answer(f"Карточки пересобраны из завершённых анкет: {synced}.")

    try:
        await message.answer_document(FSInputFile(path, filename="participants_export.csv"))
    finally:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass


@router.message(Command("admin_sync_profiles"))
async def cmd_admin_sync_profiles(message: Message, session: AsyncSession):
    if await _reject_non_admin(message):
        return

    synced = await backfill_participant_profiles(session)
    await message.answer(f"Карточки участников пересобраны: {synced}")
