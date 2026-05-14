from __future__ import annotations

from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_admin_id
from app.db.models import Questionnaire
from app.services.participant_profiles import sync_participant_profile_from_questionnaire
from app.services.questionnaire_service import (
    cancel_questionnaire,
    complete_questionnaire,
    create_questionnaire,
    get_active_questionnaire,
    get_admin_questionnaire_summary,
    get_current_question,
    get_latest_questionnaire,
    get_question_by_index,
    question_option_value,
    questionnaire_progress,
    restart_questionnaire,
    save_analysis_file,
    save_answer,
    update_question_index,
)
from data.questionnaire import QUESTIONNAIRE

router = Router()

BASE_DIR = Path(__file__).resolve().parents[2]
RECOMMENDED_TESTS_PATH = BASE_DIR / "files" / "recommended_tests.pdf"
CB_START = "q:start"
CB_RESTART = "q:restart"
CB_TESTS = "q:tests"
CB_ANSWER_PREFIX = "q:a:"
CB_ANALYSIS_UPLOAD = "q:up"
CB_ANALYSIS_SKIP = "q:skip"
CB_ANALYSIS_DONE = "q:done"


class QuestionnaireFSM(StatesGroup):
    answering = State()
    waiting_for_analysis_file = State()


def _intro_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📎 Скачать список рекомендуемых анализов",
                    callback_data=CB_TESTS,
                )
            ],
            [
                InlineKeyboardButton(
                    text="▶️ Начать анкету",
                    callback_data=CB_START,
                )
            ],
        ]
    )


def _active_intro_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Продолжить анкету", callback_data=CB_START)],
            [InlineKeyboardButton(text="🔁 Начать заново", callback_data=CB_RESTART)],
            [
                InlineKeyboardButton(
                    text="📎 Скачать список рекомендуемых анализов",
                    callback_data=CB_TESTS,
                )
            ],
        ]
    )


def _question_keyboard(question: dict) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, option in enumerate(question.get("options", [])):
        rows.append(
            [
                InlineKeyboardButton(
                    text=option,
                    callback_data=f"{CB_ANSWER_PREFIX}{question['id']}:{index}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _analysis_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📎 Да, прикрепить",
                    callback_data=CB_ANALYSIS_UPLOAD,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Пока нет",
                    callback_data=CB_ANALYSIS_SKIP,
                )
            ],
        ]
    )


def _analysis_done_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Готово",
                    callback_data=CB_ANALYSIS_DONE,
                )
            ]
        ]
    )


def _parse_number(text: str) -> float | int | None:
    normalized = text.strip().replace(",", ".")
    try:
        value = float(normalized)
    except ValueError:
        return None
    return int(value) if value.is_integer() else value


async def send_next_question(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    questionnaire: Questionnaire,
) -> None:
    question = get_current_question(questionnaire)
    if question is None:
        await finish_questionnaire(message, state, session, questionnaire)
        return

    await state.set_state(QuestionnaireFSM.answering)
    await state.update_data(questionnaire_id=questionnaire.id)
    progress, total = questionnaire_progress(questionnaire)

    text = (
        f"Вопрос {progress} из {total}\n"
        f"{question['section']}\n\n"
        f"{question['text']}"
    )

    if question["id"] == "attach_tests":
        await message.answer(text, reply_markup=_analysis_keyboard())
        return

    if question["type"] in {"single_choice", "multi_choice"}:
        await message.answer(text, reply_markup=_question_keyboard(question))
        return

    await message.answer(text)


async def _advance_to_next_question(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    questionnaire: Questionnaire,
) -> None:
    next_index = (questionnaire.current_question_index or 0) + 1
    await update_question_index(session, questionnaire.id, next_index)
    questionnaire.current_question_index = next_index
    await send_next_question(message, state, session, questionnaire)


async def finish_questionnaire(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    questionnaire: Questionnaire,
) -> None:
    completed = await complete_questionnaire(session, questionnaire.id)
    if completed is not None:
        await sync_participant_profile_from_questionnaire(session, completed.id)
    await state.clear()
    await message.answer(
        "Спасибо, анкета заполнена.\n\n"
        "Я передам ответы администратору, чтобы подготовить рекомендации."
    )

    admin_id = get_admin_id()
    if not admin_id or completed is None:
        return

    summary = await get_admin_questionnaire_summary(session, completed.id)
    try:
        await message.bot.send_message(admin_id, summary[:4000])
    except TelegramAPIError:
        return


@router.message(Command("anketa"))
async def cmd_anketa(message: Message, session: AsyncSession):
    active = await get_active_questionnaire(session, message.from_user.id)
    if active is not None:
        progress, total = questionnaire_progress(active)
        await message.answer(
            "У вас уже есть анкета в процессе.\n\n"
            f"Сейчас вы на вопросе {progress} из {total}. "
            "Можно продолжить или начать заново.",
            reply_markup=_active_intro_keyboard(),
        )
        return

    await message.answer(
        "Анкета участника программы Hey Health 🌿\n\n"
        "Она поможет лучше понять ваш образ жизни, питание и привычки, "
        "чтобы подобрать комфортные рекомендации без жёстких диет и ограничений.\n\n"
        "Заполнение займёт примерно 10-15 минут.\n\n"
        "Анализы не являются обязательными и не заменяют консультацию врача. "
        "Если они есть, сможете прикрепить их в конце анкеты.",
        reply_markup=_intro_keyboard(),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, session: AsyncSession):
    active = await get_active_questionnaire(session, message.from_user.id)
    if active:
        await cancel_questionnaire(session, active.id)
        await state.clear()
        await message.answer("Анкета отменена.")
        return

    current_state = await state.get_state()
    if current_state in {
        QuestionnaireFSM.answering.state,
        QuestionnaireFSM.waiting_for_analysis_file.state,
    }:
        await state.clear()
    await message.answer("Активной анкеты нет.")


@router.message(Command("restart_anketa"))
async def cmd_restart_anketa(message: Message, state: FSMContext, session: AsyncSession):
    questionnaire = await restart_questionnaire(session, message.from_user)
    await send_next_question(message, state, session, questionnaire)


@router.message(Command("my_anketa"))
async def cmd_my_anketa(message: Message, session: AsyncSession):
    questionnaire = await get_latest_questionnaire(session, message.from_user.id)
    if questionnaire is None:
        await message.answer("Анкета ещё не создана. Начать можно командой /anketa.")
        return

    status_map = {
        "in_progress": "в процессе",
        "completed": "завершена",
        "cancelled": "отменена",
    }
    status = status_map.get(questionnaire.status, questionnaire.status)
    if questionnaire.status == "in_progress":
        progress, total = questionnaire_progress(questionnaire)
        await message.answer(
            f"Ваша анкета: {status}.\n"
            f"Текущий прогресс: вопрос {progress} из {total}."
        )
        return

    await message.answer(f"Ваша анкета: {status}.")


@router.callback_query(F.data == CB_START)
async def on_questionnaire_start(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
):
    questionnaire = await get_active_questionnaire(session, callback.from_user.id)
    if questionnaire is None:
        questionnaire = await create_questionnaire(session, callback.from_user)

    await callback.answer()
    await send_next_question(callback.message, state, session, questionnaire)


@router.callback_query(F.data == CB_RESTART)
async def on_questionnaire_restart(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
):
    questionnaire = await restart_questionnaire(session, callback.from_user)
    await callback.answer()
    await send_next_question(callback.message, state, session, questionnaire)


@router.callback_query(F.data == CB_TESTS)
async def on_download_tests(callback: CallbackQuery):
    if RECOMMENDED_TESTS_PATH.exists():
        await callback.message.answer_document(FSInputFile(RECOMMENDED_TESTS_PATH))
    else:
        await callback.message.answer(
            "Список анализов скоро будет добавлен. Анкету можно пройти без него.\n\n"
            "Анализы не являются обязательными и не заменяют консультацию врача."
        )
    await callback.answer()


@router.callback_query(F.data.startswith(CB_ANSWER_PREFIX))
async def on_questionnaire_button_answer(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
):
    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Не удалось обработать ответ.", show_alert=True)
        return

    question_id = parts[-2]
    raw_index = parts[-1]
    questionnaire = await get_active_questionnaire(session, callback.from_user.id)
    if questionnaire is None:
        await state.clear()
        await callback.message.answer("Активная анкета не найдена. Начните заново: /anketa")
        await callback.answer()
        return

    question = get_current_question(questionnaire)
    if question is None:
        await finish_questionnaire(callback.message, state, session, questionnaire)
        await callback.answer()
        return

    if question["id"] != question_id or question["type"] not in {"single_choice", "multi_choice"}:
        await callback.answer("Это не текущий вопрос.", show_alert=True)
        return

    try:
        option_index = int(raw_index)
        answer = question_option_value(question, option_index)
    except (ValueError, IndexError):
        await callback.answer("Такого варианта нет.", show_alert=True)
        return

    await save_answer(session, questionnaire.id, question_id, answer)

    await callback.answer()
    await _advance_to_next_question(callback.message, state, session, questionnaire)


@router.callback_query(F.data == CB_ANALYSIS_UPLOAD)
async def on_analysis_upload(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    questionnaire = await get_active_questionnaire(session, callback.from_user.id)
    if questionnaire is None:
        await state.clear()
        await callback.message.answer("Активная анкета не найдена. Начните заново: /anketa")
        await callback.answer()
        return

    await save_answer(session, questionnaire.id, "attach_tests", "📎 Да, прикрепить")
    await state.set_state(QuestionnaireFSM.waiting_for_analysis_file)
    await state.update_data(questionnaire_id=questionnaire.id)
    await callback.message.answer(
        "Отправьте PDF, документ или фото анализов.\n"
        "Можно отправить несколько файлов по одному.",
        reply_markup=_analysis_done_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == CB_ANALYSIS_SKIP)
async def on_analysis_skip(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    questionnaire = await get_active_questionnaire(session, callback.from_user.id)
    if questionnaire is None:
        await state.clear()
        await callback.message.answer("Активная анкета не найдена. Начните заново: /anketa")
        await callback.answer()
        return

    await save_answer(session, questionnaire.id, "attach_tests", "Пока нет")
    await callback.answer()
    await _advance_to_next_question(callback.message, state, session, questionnaire)


@router.callback_query(F.data == CB_ANALYSIS_DONE)
async def on_analysis_done(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    questionnaire_id = data.get("questionnaire_id")
    questionnaire = (
        await session.get(Questionnaire, questionnaire_id)
        if questionnaire_id
        else await get_active_questionnaire(session, callback.from_user.id)
    )
    if questionnaire is None:
        await state.clear()
        await callback.message.answer("Активная анкета не найдена. Начните заново: /anketa")
        await callback.answer()
        return

    await callback.answer()
    await _advance_to_next_question(callback.message, state, session, questionnaire)


@router.message(QuestionnaireFSM.answering, F.text, ~F.text.startswith("/"))
async def on_questionnaire_text_answer(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
):
    questionnaire = await get_active_questionnaire(session, message.from_user.id)
    if questionnaire is None:
        await state.clear()
        await message.answer("Активная анкета не найдена. Начните заново: /anketa")
        return

    question = get_current_question(questionnaire)
    if question is None:
        await finish_questionnaire(message, state, session, questionnaire)
        return

    question_type = question["type"]
    if question_type in {"single_choice", "multi_choice"}:
        await message.answer("Пожалуйста, выберите вариант кнопкой под вопросом.")
        return

    text = (message.text or "").strip()
    if question_type == "number":
        answer = _parse_number(text)
        if answer is None:
            await message.answer("Пожалуйста, введите число. Например: 70 или 70,5.")
            return
    elif question_type == "text":
        answer = text
    else:
        await message.answer("Не удалось определить тип вопроса. Попробуйте /restart_anketa.")
        return

    await save_answer(session, questionnaire.id, question["id"], answer)
    await _advance_to_next_question(message, state, session, questionnaire)


@router.message(QuestionnaireFSM.waiting_for_analysis_file, F.document | F.photo)
async def on_analysis_file(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    questionnaire_id = data.get("questionnaire_id")
    if not questionnaire_id:
        questionnaire = await get_active_questionnaire(session, message.from_user.id)
        questionnaire_id = questionnaire.id if questionnaire else None

    if not questionnaire_id:
        await state.clear()
        await message.answer("Активная анкета не найдена. Начните заново: /anketa")
        return

    saved = await save_analysis_file(session, questionnaire_id, message)
    if saved is None:
        await message.answer("Не удалось сохранить файл. Отправьте PDF, документ или фото.")
        return

    await message.answer(
        "Файл сохранён. Можете отправить ещё один или нажать «Готово».",
        reply_markup=_analysis_done_keyboard(),
    )


@router.message(QuestionnaireFSM.waiting_for_analysis_file, F.text)
async def on_analysis_text(message: Message):
    await message.answer(
        "Нужен файл или фото анализов. Отправьте PDF, документ, фото "
        "или нажмите «Готово».",
        reply_markup=_analysis_done_keyboard(),
    )


@router.message(F.document | F.photo)
async def on_unexpected_questionnaire_file(message: Message, session: AsyncSession):
    active = await get_active_questionnaire(session, message.from_user.id)
    if active is None:
        await message.answer(
            "Сейчас бот не ждёт файл для анкеты. Начните с /anketa. "
            "Файлы анализов можно прикрепить в конце анкеты."
        )
        return

    current_question = get_current_question(active)
    if current_question and current_question["id"] == "attach_tests":
        await message.answer(
            "Сначала нажмите кнопку «📎 Да, прикрепить», "
            "после этого можно отправить PDF, документ или фото."
        )
        return

    await message.answer(
        "Сейчас бот не ждёт файл на этом шаге анкеты. "
        "Дождитесь вопроса про анализы или используйте /restart_anketa."
    )
