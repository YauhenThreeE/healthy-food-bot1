from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ParticipantNote, ParticipantProfile, Questionnaire


_MIN_DATETIME = datetime.min.replace(tzinfo=timezone.utc)


def _load_answers(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _join_name(full_name: str | None, username: str | None) -> str:
    username_text = f"@{username}" if username else "без username"
    return f"{full_name or 'без имени'} ({username_text})"


def _value(answers: dict[str, Any], key: str) -> str:
    value = answers.get(key)
    if value is None or value == "":
        return "—"
    if isinstance(value, list):
        text = ", ".join(str(item) for item in value)
    elif isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = str(value)
    text = text.strip()
    return text or "—"


def _build_profile_payload(questionnaire: Questionnaire) -> dict[str, Any]:
    answers = _load_answers(questionnaire.answers_json)
    analyses_attached = bool(questionnaire.files)
    return {
        "telegram": {
            "telegram_user_id": questionnaire.telegram_user_id,
            "username": questionnaire.username or "",
            "full_name": questionnaire.full_name or "",
        },
        "main": {
            "name": _value(answers, "name"),
            "age": _value(answers, "age"),
            "height_cm": _value(answers, "height_cm"),
            "current_weight_kg": _value(answers, "current_weight_kg"),
            "desired_weight_kg": _value(answers, "desired_weight_kg"),
        },
        "lifestyle": {
            "day_routine": _value(answers, "day_routine"),
            "daily_steps": _value(answers, "daily_steps"),
            "workouts": _value(answers, "workouts"),
            "sleep_hours": _value(answers, "sleep_hours"),
            "stress_level": _value(answers, "stress_level"),
        },
        "nutrition": {
            "meals_per_day": _value(answers, "meals_per_day"),
            "snacks": _value(answers, "snacks"),
            "water_per_day": _value(answers, "water_per_day"),
            "sweets_frequency": _value(answers, "sweets_frequency"),
            "fastfood_frequency": _value(answers, "fastfood_frequency"),
            "alcohol": _value(answers, "alcohol"),
            "night_overeating": _value(answers, "night_overeating"),
            "food_breakdowns": _value(answers, "food_breakdowns"),
        },
        "health": {
            "chronic_diseases": _value(answers, "chronic_diseases"),
            "gi_problems": _value(answers, "gi_problems"),
            "medications_or_supplements": _value(answers, "medications_or_supplements"),
            "energy_level": _value(answers, "energy_level"),
            "sleep_problems": _value(answers, "sleep_problems"),
            "swelling": _value(answers, "swelling"),
            "cycle_regular": _value(answers, "cycle_regular"),
        },
        "goals": {
            "why_lose_weight": _value(answers, "why_lose_weight"),
            "main_difficulty": _value(answers, "main_difficulty"),
            "expectations": _value(answers, "expectations"),
            "time_available": _value(answers, "time_available"),
            "month_result": _value(answers, "month_result"),
        },
        "analyses": {
            "attach_tests": _value(answers, "attach_tests"),
            "attached": analyses_attached,
            "files_count": len(questionnaire.files),
        },
    }


def _build_summary_text(payload: dict[str, Any]) -> str:
    main = payload["main"]
    lifestyle = payload["lifestyle"]
    nutrition = payload["nutrition"]
    health = payload["health"]
    goals = payload["goals"]
    analyses = payload["analyses"]
    return (
        f"Участник: {_join_name(payload['telegram']['full_name'], payload['telegram']['username'])}\n"
        f"Имя из анкеты: {main['name']}\n"
        f"Цель: {goals['why_lose_weight']}\n"
        f"Главная сложность: {goals['main_difficulty']}\n"
        f"Возраст/рост/вес: {main['age']} / {main['height_cm']} / {main['current_weight_kg']}\n"
        f"Желаемый вес: {main['desired_weight_kg']}\n"
        f"День: {lifestyle['day_routine']}\n"
        f"Шаги/тренировки: {lifestyle['daily_steps']} / {lifestyle['workouts']}\n"
        f"Сон/стресс: {lifestyle['sleep_hours']} / {lifestyle['stress_level']}\n"
        f"Приёмы пищи/вода: {nutrition['meals_per_day']} / {nutrition['water_per_day']}\n"
        f"Перекусы/срывы: {nutrition['snacks']} / {nutrition['food_breakdowns']}\n"
        f"ЖКТ/энергия/отёки: {health['gi_problems']} / {health['energy_level']} / {health['swelling']}\n"
        f"Анализы: {'прикреплены' if analyses['attached'] else 'не прикреплены'}"
    )


def _build_risk_flags_text(payload: dict[str, Any]) -> str:
    health = payload["health"]
    lifestyle = payload["lifestyle"]
    nutrition = payload["nutrition"]
    flags: list[str] = []

    for label, value in [
        ("Хронические заболевания", health["chronic_diseases"]),
        ("Проблемы ЖКТ", health["gi_problems"]),
        ("Низкая энергия", health["energy_level"]),
        ("Проблемы со сном", health["sleep_problems"]),
        ("Отёки", health["swelling"]),
        ("Высокий стресс", lifestyle["stress_level"]),
        ("Ночные переедания", nutrition["night_overeating"]),
        ("Частые срывы", nutrition["food_breakdowns"]),
    ]:
        if value != "—" and value.lower() not in {"нет", "редко", "низкий"}:
            flags.append(f"{label}: {value}")

    return "\n".join(flags) if flags else "Явные флаги риска не отмечены."


def _build_coach_focus_text(payload: dict[str, Any]) -> str:
    goals = payload["goals"]
    lifestyle = payload["lifestyle"]
    nutrition = payload["nutrition"]
    return (
        "Фокус ведущего:\n"
        f"- Основная цель: {goals['why_lose_weight']}\n"
        f"- Главное препятствие: {goals['main_difficulty']}\n"
        f"- Режим дня: {lifestyle['day_routine']}\n"
        f"- Питание: {nutrition['meals_per_day']} приёмов, перекусы: {nutrition['snacks']}\n"
        f"- Сколько времени готов уделять: {goals['time_available']}\n"
        f"- Ожидания на месяц: {goals['month_result']}"
    )


async def get_participant_profile(
    session: AsyncSession,
    telegram_user_id: int,
) -> ParticipantProfile | None:
    result = await session.execute(
        select(ParticipantProfile)
        .options(selectinload(ParticipantProfile.notes))
        .where(ParticipantProfile.telegram_user_id == telegram_user_id)
    )
    return result.scalar_one_or_none()


async def _sync_from_latest_completed_questionnaire(
    session: AsyncSession,
    telegram_user_id: int,
) -> ParticipantProfile | None:
    result = await session.execute(
        select(Questionnaire)
        .where(
            Questionnaire.telegram_user_id == telegram_user_id,
            Questionnaire.status == "completed",
        )
        .order_by(Questionnaire.completed_at.desc(), Questionnaire.id.desc())
        .limit(1)
    )
    questionnaire = result.scalar_one_or_none()
    if questionnaire is None:
        return None
    return await sync_participant_profile_from_questionnaire(session, questionnaire.id)


async def backfill_participant_profiles(session: AsyncSession) -> int:
    result = await session.execute(
        select(Questionnaire)
        .options(selectinload(Questionnaire.files))
        .where(Questionnaire.status == "completed")
        .order_by(Questionnaire.completed_at.desc(), Questionnaire.id.desc())
    )
    questionnaires = list(result.scalars())
    synced = 0
    seen_telegram_ids: set[int] = set()
    for questionnaire in questionnaires:
        if questionnaire.telegram_user_id in seen_telegram_ids:
            continue
        seen_telegram_ids.add(questionnaire.telegram_user_id)
        profile = await sync_participant_profile_from_questionnaire(session, questionnaire.id)
        if profile is not None:
            synced += 1
    return synced


async def sync_participant_profile_by_questionnaire_id(
    session: AsyncSession,
    questionnaire_id: int,
) -> ParticipantProfile | None:
    return await sync_participant_profile_from_questionnaire(session, questionnaire_id)


async def sync_participant_profile_from_questionnaire(
    session: AsyncSession,
    questionnaire_id: int,
) -> ParticipantProfile | None:
    result = await session.execute(
        select(Questionnaire)
        .options(selectinload(Questionnaire.files))
        .where(Questionnaire.id == questionnaire_id)
    )
    questionnaire = result.scalar_one_or_none()
    if questionnaire is None:
        return None

    profile = await get_participant_profile(session, questionnaire.telegram_user_id)
    payload = _build_profile_payload(questionnaire)
    if profile is None:
        profile = ParticipantProfile(telegram_user_id=questionnaire.telegram_user_id)
        session.add(profile)

    profile.username = questionnaire.username
    profile.telegram_full_name = questionnaire.full_name
    profile.questionnaire_id = questionnaire.id
    profile.questionnaire_status = questionnaire.status
    profile.profile_json = json.dumps(payload, ensure_ascii=False, default=str)
    profile.summary_text = _build_summary_text(payload)
    profile.risk_flags_text = _build_risk_flags_text(payload)
    profile.coach_focus_text = _build_coach_focus_text(payload)
    await session.flush()
    return profile


async def add_participant_note(
    session: AsyncSession,
    telegram_user_id: int,
    note_text: str,
    author_telegram_id: int | None = None,
    source: str = "admin",
) -> ParticipantNote | None:
    clean_text = note_text.strip()
    if not clean_text:
        return None

    profile = await get_participant_profile(session, telegram_user_id)
    if profile is None:
        profile = await _sync_from_latest_completed_questionnaire(session, telegram_user_id)
    if profile is None:
        return None

    note = ParticipantNote(
        participant_profile_id=profile.id,
        telegram_user_id=telegram_user_id,
        author_telegram_id=author_telegram_id,
        source=source,
        note_text=clean_text,
    )
    session.add(note)
    await session.flush()
    return note


async def get_participant_card_text(
    session: AsyncSession,
    telegram_user_id: int,
) -> str:
    result = await session.execute(
        select(ParticipantProfile)
        .options(selectinload(ParticipantProfile.notes))
        .where(ParticipantProfile.telegram_user_id == telegram_user_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = await _sync_from_latest_completed_questionnaire(session, telegram_user_id)
    if profile is None:
        return "Карточка участника не найдена. Возможно, анкета ещё не завершена."

    notes = sorted(profile.notes, key=lambda item: item.created_at or _MIN_DATETIME, reverse=True)[:5]
    notes_block = "\n".join(
        f"- {note.created_at:%Y-%m-%d %H:%M}: {note.note_text}" if note.created_at else f"- {note.note_text}"
        for note in notes
    ) or "—"

    return (
        "Карточка участника\n"
        f"Telegram ID: {profile.telegram_user_id}\n"
        f"Пользователь: {_join_name(profile.telegram_full_name, profile.username)}\n"
        f"Статус анкеты: {profile.questionnaire_status or '—'}\n\n"
        f"{profile.summary_text}\n\n"
        f"Риски:\n{profile.risk_flags_text}\n\n"
        f"{profile.coach_focus_text}\n\n"
        f"Последние заметки:\n{notes_block}"
    )


async def get_participant_notes_text(
    session: AsyncSession,
    telegram_user_id: int,
) -> str:
    profile = await get_participant_profile(session, telegram_user_id)
    if profile is None:
        profile = await _sync_from_latest_completed_questionnaire(session, telegram_user_id)
    if profile is None:
        return "Карточка участника не найдена."

    notes = sorted(profile.notes, key=lambda item: item.created_at or _MIN_DATETIME, reverse=True)
    if not notes:
        return "Заметок по участнику пока нет."

    lines = [f"Заметки по участнику {telegram_user_id}:"]
    for note in notes[:20]:
        prefix = note.created_at.strftime("%Y-%m-%d %H:%M") if note.created_at else "без даты"
        lines.append(f"- {prefix}: {note.note_text}")
    return "\n".join(lines)


async def export_participants_csv(session: AsyncSession) -> Path | None:
    result = await session.execute(
        select(ParticipantProfile).order_by(ParticipantProfile.updated_at.desc(), ParticipantProfile.id.desc())
    )
    profiles = list(result.scalars())
    if not profiles:
        return None

    tmp = NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".csv", delete=False)
    path = Path(tmp.name)
    with tmp:
        writer = csv.writer(tmp)
        writer.writerow(
            [
                "telegram_user_id",
                "username",
                "telegram_full_name",
                "questionnaire_status",
                "summary_text",
                "risk_flags_text",
                "coach_focus_text",
                "updated_at",
            ]
        )
        for profile in profiles:
            writer.writerow(
                [
                    profile.telegram_user_id,
                    profile.username or "",
                    profile.telegram_full_name or "",
                    profile.questionnaire_status or "",
                    profile.summary_text or "",
                    profile.risk_flags_text or "",
                    profile.coach_focus_text or "",
                    profile.updated_at.isoformat() if profile.updated_at else "",
                ]
            )
    return path
