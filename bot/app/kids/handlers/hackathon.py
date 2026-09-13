"""Команды на хакатон: капитан создаёт, остальные вступают по ссылке-коду.

Это и заполняет students.team в менторской базе — то, что раньше приходилось
вбивать руками. Пока команды могут собираться из разных групп: сузить до
одной группы — отдельная будущая правка (см. db.join_hack_team).
"""
from __future__ import annotations

import logging
import secrets

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app import db
from app.config import settings
from app.kids import keyboards as kb

log = logging.getLogger(__name__)
router = Router(name="kids-hackathon")


class Team(StatesGroup):
    naming = State()
    casing = State()
    joining = State()


def _join_link(code: str) -> str:
    if not settings.kids_bot_username:
        return f"код: {code}"
    return f"https://t.me/{settings.kids_bot_username}?start=team_{code}"


async def _team_card(team, members) -> str:
    names = "\n".join(f"  {i}. {m['full_name']}" for i, m in enumerate(members, 1))
    lines = [
        f"<b>{team['name']}</b>",
        f"Кейс: {team['case_name']}" if team["case_name"] else "Кейс пока не выбран",
        f"\nУчастники ({len(members)}):\n{names}",
        f"\nЗови ещё: {_join_link(team['join_code'])}",
    ]
    return "\n".join(lines)


@router.message(F.text == "🏆 Моя команда")
@router.message(Command("team"))
async def team_entry(message: Message, state: FSMContext) -> None:
    await state.clear()
    student = await db.student_by_tg(message.from_user.id)
    if not student:
        await message.answer("Сначала зарегистрируйся: /start")
        return

    team = await db.hack_team_of_student(student["id"])
    if team:
        members = await db.hack_team_members(team["id"])
        await message.answer(await _team_card(team, members), reply_markup=kb.team_card(team["join_code"]))
        return

    await message.answer(
        "У тебя пока нет команды на хакатон.",
        reply_markup=kb.team_entry(),
    )


@router.callback_query(F.data == "team:create")
async def create_start(call: CallbackQuery, state: FSMContext) -> None:
    student = await db.student_by_tg(call.from_user.id)
    if not student:
        await call.answer("Сначала /start", show_alert=True)
        return
    existing = await db.hack_team_of_student(student["id"])
    if existing:
        await call.answer("Ты уже в команде", show_alert=True)
        return
    await state.update_data(student_id=student["id"])
    await state.set_state(Team.naming)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer()
    await call.message.answer("Как назовём команду?")


@router.message(Team.naming, F.text)
async def got_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name or name.startswith("/"):
        await message.answer("Нужно название текстом — например, «Nova».")
        return
    await state.update_data(team_name=name)
    await state.set_state(Team.casing)
    await message.answer(
        "Какой кейс берёте? Можно пропустить и решить позже.",
        reply_markup=kb.team_skip_case(),
    )


@router.message(Team.casing, F.text)
async def got_case(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if text.startswith("/"):
        await message.answer("Жду название кейса или «Пока без кейса».")
        return
    await _create_team(message, state, text)


@router.callback_query(F.data == "team:skip_case", Team.casing)
async def skip_case(call: CallbackQuery, state: FSMContext) -> None:
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer()
    await _create_team(call.message, state, None)


async def _create_team(message: Message, state: FSMContext, case_name: str | None) -> None:
    data = await state.get_data()
    code = None
    for _ in range(5):
        candidate = secrets.token_urlsafe(4)
        if not await db.hack_team_by_code(candidate):
            code = candidate
            break
    await state.clear()
    if code is None:
        await message.answer("Не смог сгенерировать код команды, попробуй ещё раз /team.")
        return

    team_id = await db.create_hack_team(data["team_name"], case_name, data["student_id"], code)
    team = await db.hack_team_by_code(code)
    members = await db.hack_team_members(team_id)
    await message.answer(
        f"Команда создана!\n\n{await _team_card(team, members)}",
        reply_markup=kb.team_card(code),
    )


@router.callback_query(F.data == "team:join")
async def join_start(call: CallbackQuery, state: FSMContext) -> None:
    student = await db.student_by_tg(call.from_user.id)
    if not student:
        await call.answer("Сначала /start", show_alert=True)
        return
    if await db.hack_team_of_student(student["id"]):
        await call.answer("Ты уже в команде", show_alert=True)
        return
    await state.set_state(Team.joining)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer()
    await call.message.answer("Пришли код от капитана (или просто открой его ссылку).")


@router.message(Team.joining, F.text)
async def got_code(message: Message, state: FSMContext) -> None:
    await state.clear()
    code = message.text.strip()
    await _join_by_code(message, code)


@router.message(Command("join"))
async def join_cmd(message: Message, command: CommandObject) -> None:
    code = (command.args or "").strip()
    if not code:
        await message.answer("Формат: /join КОД")
        return
    await _join_by_code(message, code)


async def _join_by_code(message: Message, code: str) -> None:
    student = await db.student_by_tg(message.from_user.id)
    if not student:
        await message.answer("Сначала зарегистрируйся: /start")
        return
    existing = await db.hack_team_of_student(student["id"])
    if existing:
        await message.answer(f"Ты уже в команде «{existing['name']}».")
        return

    team = await db.hack_team_by_code(code)
    if not team:
        await message.answer("Не нашёл команду с таким кодом — сверься с капитаном.")
        return

    await db.join_hack_team(team["id"], student["id"])
    members = await db.hack_team_members(team["id"])
    await message.answer(
        f"Готово, ты в команде!\n\n{await _team_card(team, members)}",
        reply_markup=kb.team_card(code),
    )


@router.callback_query(F.data == "team:leave")
async def leave_team(call: CallbackQuery) -> None:
    student = await db.student_by_tg(call.from_user.id)
    if not student:
        await call.answer("Сначала /start", show_alert=True)
        return
    await db.leave_hack_team(student["id"])
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer("Вышел из команды")
    await call.message.answer("Ты вышел из команды. Создать новую или вступить в другую — /team.")


@router.message(Command("stop"), Team.naming)
@router.message(Command("stop"), Team.casing)
@router.message(Command("stop"), Team.joining)
async def stop_team(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Ок, отменил. Вернуться к команде — /team.")


async def handle_team_deep_link(message: Message, code: str) -> None:
    """Вызывается из registration.py при /start?start=team_<code> —
    единая точка разбора deep link'ов, чтобы team_ и inv_ не спорили за
    приоритет между хендлерами (см. докстринг в registration.py)."""
    student = await db.student_by_tg(message.from_user.id)
    if not student:
        await message.answer(
            "Это ссылка на команду. Сначала зарегистрируйся: пришли /start и "
            "поделись номером, потом открой эту ссылку ещё раз."
        )
        return
    await _join_by_code(message, code)
