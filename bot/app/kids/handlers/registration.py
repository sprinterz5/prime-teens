"""Вход ученика: по персональной ссылке от наставника или по номеру телефона.

По-хорошему в базе должны оказаться все — поэтому оба пути равноправны:
ссылка (см. /invite → «Ссылки для учеников» в боте ментора) сразу знает,
кто это, а голый /start + контакт ищет ученика по номеру телефона среди
того, что загружено Excel-импортом/Google-таблицей (students.phone).
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app import db
from app.kids import keyboards as kb
from app.kids.handlers import hackathon

log = logging.getLogger(__name__)
router = Router(name="kids-registration")


class Onboarding(StatesGroup):
    invited = State()  # пришёл по ссылке — ждём контакт, чтобы её погасить


def _welcome_text(student) -> str:
    bits = [f"класс {student['class_school']}" if student["class_school"] else None,
            f"команда «{student['team']}»" if student["team"] else None]
    tail = " · ".join(b for b in bits if b)
    return (f"Привет, {student['full_name']}!" + (f"\n{tail}" if tail else "") +
            "\n\nЯ буду напоминать о занятиях и собирать твой отзыв после урока — "
            "он уходит наставнику без твоего имени.")


async def _welcome(message: Message, student) -> None:
    await message.answer(_welcome_text(student), reply_markup=kb.main_menu())


@router.message(CommandStart(deep_link=True))
async def start_deep_link(message: Message, command: CommandObject, state: FSMContext) -> None:
    """t.me/<kids_bot>?start=inv_<token> — персональная ссылка (см. /invite
    в боте ментора). t.me/<kids_bot>?start=team_<code> — вступление в
    команду на хакатон.

    Оба разбираются ЗДЕСЬ, в одном хендлере, а не в двух разных модулях: у
    aiogram первый совпавший по фильтру CommandStart(deep_link=True)
    хендлер обрабатывает апдейт целиком (не важно, распознал ли он
    payload) — второй такой же хендлер в другом роутере просто не получит
    шанса сработать. Поэтому вся диспетчеризация по префиксу — тут, а
    сама логика вступления в команду вынесена в
    hackathon.handle_team_deep_link, чтобы не дублировать её."""
    payload = (command.args or "").strip()
    if payload.startswith("team_"):
        await hackathon.handle_team_deep_link(message, payload[len("team_"):])
        return
    if not payload.startswith("inv_"):
        await start(message)
        return

    token = payload[len("inv_"):]
    invite = await db.invite_by_token(token)
    status = await db.invite_status(token, message.from_user.id)

    if status in ("not_found", "revoked"):
        await message.answer(
            "Эта ссылка недействительна или уже отозвана.\n"
            "Попроси у наставника новую, либо просто /start и поделись номером."
        )
        return
    if status == "used_by_other":
        await message.answer(
            "Эта ссылка уже использована — она одноразовая.\n"
            "Попроси у наставника новую."
        )
        return
    if invite["student_id"] is None:
        await message.answer(
            "Эта ссылка не для ученического бота. Попроси у наставника верную."
        )
        return
    if status == "used_by_self":
        student = await db.student(invite["student_id"])
        if student:
            await _welcome(message, student)
        else:
            await start(message)
        return

    await state.update_data(invite_token=token, invite_student_id=invite["student_id"])
    await state.set_state(Onboarding.invited)
    student = await db.student(invite["student_id"])
    name = student["full_name"] if student else "тебя"
    await message.answer(
        f"Привет! Эта ссылка для {name}.\n\n"
        "Подтверди номер телефона, чтобы я знал, кто ты — так твой наставник "
        "увидит, что ты подключился.",
        reply_markup=kb.share_phone(),
    )


@router.message(CommandStart())
async def start(message: Message) -> None:
    student = await db.student_by_tg(message.from_user.id)
    if student:
        await _welcome(message, student)
        return
    await message.answer(
        "<b>PrimeTeens · бот для учеников</b>\n\n"
        "Я напоминаю о занятиях, собираю отзыв после урока (наставник видит его "
        "без твоего имени) и помогаю собрать команду на хакатон.\n\n"
        "Подтверди номер телефона — по нему найду тебя в списке твоей группы.",
        reply_markup=kb.share_phone(),
    )


@router.message(F.contact)
async def got_contact(message: Message, state: FSMContext) -> None:
    contact = message.contact
    if contact.user_id != message.from_user.id:
        await message.answer(
            "Это чужой контакт. Нужен именно твой номер — нажми кнопку «Поделиться номером».",
            reply_markup=kb.share_phone(),
        )
        return

    phone = db.norm_phone(contact.phone_number)
    data = await state.get_data()
    invite_token = data.get("invite_token")

    if invite_token:
        await state.clear()
        status = await db.invite_status(invite_token, message.from_user.id)
        if status in ("not_found", "revoked"):
            await message.answer(
                "Пока ты нажимал «Поделиться номером», ссылку успели отозвать.\n"
                "Попроси у наставника новую.",
                reply_markup=kb.REMOVE,
            )
            return
        if status == "used_by_other":
            await message.answer(
                "Пока ты нажимал «Поделиться номером», ссылку успели использовать.\n"
                "Попроси у наставника новую.",
                reply_markup=kb.REMOVE,
            )
            return

        await db.claim_invite(invite_token, message.from_user.id)
        student_id = data["invite_student_id"]
        await db.link_student_tg(student_id, message.from_user.id, phone=phone)
        student = await db.student(student_id)
        await _welcome(message, student)
        return

    matches = await db.q(
        """SELECT s.*, g.name AS group_name FROM students s
           JOIN groups g ON g.id = s.group_id
           WHERE s.phone = ? AND s.active = 1 ORDER BY s.full_name""",
        phone,
    )
    if not matches:
        await message.answer(
            f"Номер <code>+{phone}</code> не нашёлся в списке учеников.\n\n"
            "Попроси наставника или админа проверить, что твой номер есть в "
            "таблице курса — я подключусь автоматически, как только он там появится.",
            reply_markup=kb.REMOVE,
        )
        return

    if len(matches) == 1:
        await _claim_student(message, matches[0])
        return

    await message.answer(
        "По этому номеру нашлось несколько учеников (бывает — семейный телефон). "
        "Кто из них ты?",
        reply_markup=kb.pick_self(matches),
    )


@router.callback_query(F.data.startswith("me:"))
async def pick_self(call: CallbackQuery) -> None:
    student_id = int(call.data.split(":")[1])
    student = await db.student(student_id)
    if not student:
        await call.answer("Не нашёл — попробуй ещё раз /start", show_alert=True)
        return
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer()
    await _claim_student(call.message, student, tg_user_id=call.from_user.id)


async def _claim_student(message: Message, student, tg_user_id: int | None = None) -> None:
    tg_id = tg_user_id if tg_user_id is not None else message.from_user.id
    if student["tg_user_id"] and student["tg_user_id"] != tg_id:
        await message.answer(
            "Этот номер уже привязан к другому Telegram-аккаунту. "
            "Если это ошибка — попроси наставника разобраться.",
            reply_markup=kb.REMOVE,
        )
        return
    await db.link_student_tg(student["id"], tg_id)
    student = await db.student(student["id"])
    await _welcome(message, student)


@router.message(Command("whoami"))
async def whoami(message: Message) -> None:
    student = await db.student_by_tg(message.from_user.id)
    lines = [f"<b>Твой Telegram ID:</b> <code>{message.from_user.id}</code>"]
    if student:
        lines.append(f"В базе: {student['full_name']}, телефон {student['phone'] or '—'}")
    await message.answer("\n".join(lines))
