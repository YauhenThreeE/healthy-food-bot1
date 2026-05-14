from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Questionnaire, QuestionnaireFile
from data.questionnaire import QUESTIONNAIRE


STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"


def _full_name_from_user(user: Any) -> str:
    parts = [
        getattr(user, "first_name", None),
        getattr(user, "last_name", None),
    ]
    return " ".join(part for part in parts if part) or ""


def _telegram_user_id(user: Any) -> int:
    return getattr(user, "telegram_id", None) or getattr(user, "id")


def _load_answers(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _dump_answers(answers: dict[str, Any]) -> str:
    return json.dumps(answers, ensure_ascii=False, default=str)


def _format_answer(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return _dump_answers(value)
    return str(value)


def _answer(answers: dict[str, Any], question_id: str) -> str:
    value = answers.get(question_id)
    if value is None or value == "":
        return "—"
    text = _format_answer(value).strip()
    return text or "—"


async def get_active_questionnaire(
    session: AsyncSession,
    telegram_user_id: int,
) -> Questionnaire | None:
    result = await session.execute(
        select(Questionnaire)
        .where(
            Questionnaire.telegram_user_id == telegram_user_id,
            Questionnaire.status == STATUS_IN_PROGRESS,
        )
        .order_by(Questionnaire.created_at.desc(), Questionnaire.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_questionnaire(
    session: AsyncSession,
    telegram_user_id: int,
) -> Questionnaire | None:
    result = await session.execute(
        select(Questionnaire)
        .where(Questionnaire.telegram_user_id == telegram_user_id)
        .order_by(Questionnaire.created_at.desc(), Questionnaire.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def get_question_by_index(index: int) -> dict[str, Any] | None:
    if index < 0 or index >= len(QUESTIONNAIRE):
        return None
    return QUESTIONNAIRE[index]


def get_current_question(questionnaire: Questionnaire) -> dict[str, Any] | None:
    return get_question_by_index(questionnaire.current_question_index or 0)


def questionnaire_progress(questionnaire: Questionnaire) -> tuple[int, int]:
    total = len(QUESTIONNAIRE)
    index = questionnaire.current_question_index or 0
    return min(index + 1, total), total


def question_option_value(question: dict[str, Any], option_index: int) -> Any:
    option = question["options"][option_index]
    if question["type"] == "multi_choice":
        return [option]
    return option


async def create_questionnaire(
    session: AsyncSession,
    user: Any,
) -> Questionnaire:
    questionnaire = Questionnaire(
        telegram_user_id=_telegram_user_id(user),
        username=getattr(user, "username", None),
        full_name=_full_name_from_user(user),
        status=STATUS_IN_PROGRESS,
        answers_json="{}",
        current_question_index=0,
    )
    session.add(questionnaire)
    await session.flush()
    return questionnaire


async def save_answer(
    session: AsyncSession,
    questionnaire_id: int,
    question_id: str,
    answer: Any,
) -> Questionnaire | None:
    questionnaire = await session.get(Questionnaire, questionnaire_id)
    if questionnaire is None:
        return None

    answers = _load_answers(questionnaire.answers_json)
    answers[question_id] = answer
    questionnaire.answers_json = _dump_answers(answers)
    await session.flush()
    return questionnaire


async def update_question_index(
    session: AsyncSession,
    questionnaire_id: int,
    index: int,
) -> Questionnaire | None:
    questionnaire = await session.get(Questionnaire, questionnaire_id)
    if questionnaire is None:
        return None

    questionnaire.current_question_index = index
    await session.flush()
    return questionnaire


async def complete_questionnaire(
    session: AsyncSession,
    questionnaire_id: int,
) -> Questionnaire | None:
    questionnaire = await session.get(Questionnaire, questionnaire_id)
    if questionnaire is None:
        return None

    questionnaire.status = STATUS_COMPLETED
    questionnaire.completed_at = datetime.now(timezone.utc)
    await session.flush()
    return questionnaire


async def cancel_questionnaire(
    session: AsyncSession,
    questionnaire_id: int,
) -> Questionnaire | None:
    questionnaire = await session.get(Questionnaire, questionnaire_id)
    if questionnaire is None:
        return None

    questionnaire.status = STATUS_CANCELLED
    await session.flush()
    return questionnaire


async def restart_questionnaire(
    session: AsyncSession,
    user: Any,
) -> Questionnaire:
    active = await get_active_questionnaire(session, _telegram_user_id(user))
    if active is not None:
        active.status = STATUS_CANCELLED
        await session.flush()
    return await create_questionnaire(session, user)


async def save_analysis_file(
    session: AsyncSession,
    questionnaire_id: int,
    message: Any,
) -> QuestionnaireFile | None:
    questionnaire = await session.get(Questionnaire, questionnaire_id)
    if questionnaire is None:
        return None

    document = getattr(message, "document", None)
    photos = getattr(message, "photo", None) or []
    photo = photos[-1] if photos else None
    file_obj = document or photo
    if file_obj is None:
        return None

    from_user = getattr(message, "from_user", None)
    telegram_user_id = (
        getattr(from_user, "id", None)
        or questionnaire.telegram_user_id
    )
    questionnaire_file = QuestionnaireFile(
        questionnaire_id=questionnaire.id,
        telegram_user_id=telegram_user_id,
        file_id=file_obj.file_id,
        file_unique_id=getattr(file_obj, "file_unique_id", None),
        file_name=getattr(document, "file_name", None) if document else None,
        mime_type=getattr(document, "mime_type", None) if document else "image/jpeg",
    )
    session.add(questionnaire_file)
    await session.flush()
    return questionnaire_file


async def get_questionnaire_summary(
    session: AsyncSession,
    questionnaire_id: int,
) -> str:
    result = await session.execute(
        select(Questionnaire)
        .options(selectinload(Questionnaire.files))
        .where(Questionnaire.id == questionnaire_id)
    )
    questionnaire = result.scalar_one_or_none()
    if questionnaire is None:
        return "Анкета не найдена."

    answers = _load_answers(questionnaire.answers_json)
    lines = [
        "Анкета участника:",
        f"ID анкеты: {questionnaire.id}",
        f"Telegram ID: {questionnaire.telegram_user_id}",
        f"Имя: {questionnaire.full_name or '-'}",
        f"Username: @{questionnaire.username}" if questionnaire.username else "Username: -",
        f"Статус: {questionnaire.status}",
        f"Прогресс: {len(answers)} / {len(QUESTIONNAIRE)}",
        f"Файлов анализов: {len(questionnaire.files)}",
        "",
        "Ответы:",
    ]

    for question in QUESTIONNAIRE:
        question_id = question["id"]
        if question_id not in answers:
            continue
        text = question["text"]
        answer = _format_answer(answers[question_id])
        lines.append(f"- {text}: {answer}")

    return "\n".join(lines)


async def get_admin_questionnaire_summary(
    session: AsyncSession,
    questionnaire_id: int,
) -> str:
    result = await session.execute(
        select(Questionnaire)
        .options(selectinload(Questionnaire.files))
        .where(Questionnaire.id == questionnaire_id)
    )
    questionnaire = result.scalar_one_or_none()
    if questionnaire is None:
        return "Анкета не найдена."

    answers = _load_answers(questionnaire.answers_json)
    analyses_status = "прикреплены" if questionnaire.files else "не прикреплены"
    username = f"@{questionnaire.username}" if questionnaire.username else "—"

    lines = [
        "Новая анкета ✅",
        "",
        "Пользователь:",
        f"- Telegram ID: {questionnaire.telegram_user_id}",
        f"- Username: {username}",
        f"- Имя в Telegram: {questionnaire.full_name or '—'}",
        "",
        "Основное:",
        f"- Имя: {_answer(answers, 'name')}",
        f"- Возраст: {_answer(answers, 'age')}",
        f"- Рост: {_answer(answers, 'height_cm')}",
        f"- Текущий вес: {_answer(answers, 'current_weight_kg')}",
        f"- Желаемый вес: {_answer(answers, 'desired_weight_kg')}",
        "",
        "Образ жизни:",
        f"- День: {_answer(answers, 'day_routine')}",
        f"- Шаги: {_answer(answers, 'daily_steps')}",
        f"- Тренировки: {_answer(answers, 'workouts')}",
        f"- Сон: {_answer(answers, 'sleep_hours')}",
        f"- Стресс: {_answer(answers, 'stress_level')}",
        "",
        "Питание:",
        f"- Приёмы пищи: {_answer(answers, 'meals_per_day')}",
        f"- Перекусы: {_answer(answers, 'snacks')}",
        f"- Вода: {_answer(answers, 'water_per_day')}",
        f"- Сладкое: {_answer(answers, 'sweets_frequency')}",
        f"- Фастфуд: {_answer(answers, 'fastfood_frequency')}",
        f"- Алкоголь: {_answer(answers, 'alcohol')}",
        f"- Ночные переедания: {_answer(answers, 'night_overeating')}",
        f"- Срывы: {_answer(answers, 'food_breakdowns')}",
        "",
        "Здоровье:",
        f"- Хронические заболевания: {_answer(answers, 'chronic_diseases')}",
        f"- ЖКТ: {_answer(answers, 'gi_problems')}",
        f"- Лекарства/БАДы: {_answer(answers, 'medications_or_supplements')}",
        f"- Энергия: {_answer(answers, 'energy_level')}",
        f"- Сон: {_answer(answers, 'sleep_problems')}",
        f"- Отёки: {_answer(answers, 'swelling')}",
        f"- Цикл: {_answer(answers, 'cycle_regular')}",
        "",
        "Цели:",
        f"- Почему хочет похудеть: {_answer(answers, 'why_lose_weight')}",
        f"- Что самое сложное: {_answer(answers, 'main_difficulty')}",
        f"- Ожидания: {_answer(answers, 'expectations')}",
        f"- Сколько времени готов уделять: {_answer(answers, 'time_available')}",
        f"- Хороший результат через месяц: {_answer(answers, 'month_result')}",
        "",
        "Анализы:",
        f"- {analyses_status}",
    ]
    return "\n".join(lines)
