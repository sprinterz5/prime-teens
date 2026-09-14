"""Сборка характеристик: заметки -> LLM -> HTML-документ."""
from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, Message

from app import db, keyboards as kb, llm, render
from app.config import COURSE

log = logging.getLogger(__name__)
router = Router(name="characteristics")


@router.message(F.text == "🧪 Характеристики (эксперимент)")
@router.message(Command("characteristics"))
async def entry(message: Message) -> None:
    mentor = await db.mentor_by_tg(message.from_user.id)
    if not mentor:
        await message.answer("Сначала зарегистрируйся: /start")
        return
    groups = await db.mentor_groups(mentor["id"])
    if not groups:
        await message.answer("К тебе не привязана группа.")
        return
    await message.answer(
        "🧪 <b>Экспериментальная функция.</b>\n\n"
        "Модель пишет черновик характеристики по заметкам менторов. Она честно "
        "старается ничего не выдумывать, но всё равно может переставить акценты, "
        "приукрасить или сгладить неудобное. <b>Каждый документ надо перечитать "
        "перед тем, как показывать родителям.</b>\n\n"
        "Основной способ — забрать материалы и написать самому: /export"
    )
    if len(groups) > 1:
        await message.answer("Какая группа?", reply_markup=kb.pick_group(groups, "ch:group"))
        return
    await _show_students(message, groups[0]["id"])


@router.callback_query(F.data.startswith("ch:group:"))
async def pick_group(call: CallbackQuery) -> None:
    gid = int(call.data.split(":")[2])
    await call.message.edit_reply_markup(reply_markup=None)
    await _show_students(call.message, gid)
    await call.answer()


async def _show_students(message: Message, group_id: int) -> None:
    students = await db.students(group_id)
    if not students:
        await message.answer("В группе нет учеников.")
        return

    final_done = await db.session_done(group_id, 0, "final")
    warn = "" if final_done else (
        "⚠️ Финальный опрос ещё не закрыт — документы получатся бедными. "
        "Лучше сначала /final.\n\n"
    )
    await message.answer(
        f"{warn}Кому собираем характеристику?",
        reply_markup=kb.pick_students(students, "ch:one", extra_all=f"ch:all:{group_id}"),
    )


@router.callback_query(F.data.startswith("ch:one:"))
async def one(call: CallbackQuery) -> None:
    sid = int(call.data.split(":")[2])
    await call.answer()
    await call.message.edit_reply_markup(reply_markup=None)
    await _generate_and_send(call.message, [sid])


@router.callback_query(F.data.startswith("ch:all:"))
async def all_students(call: CallbackQuery) -> None:
    gid = int(call.data.split(":")[2])
    students = await db.students(gid)
    await call.answer()
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(
        f"Собираю {len(students)} характеристик. Это займёт пару минут — "
        "буду присылать по мере готовности."
    )
    await _generate_and_send(call.message, [s["id"] for s in students])


async def _generate_and_send(message: Message, student_ids: list[int]) -> None:
    for sid in student_ids:
        student = await db.student(sid)
        if not student:
            continue
        answers = await db.student_answers(sid)
        if not answers:
            await message.answer(
                f"❌ {student['full_name']}: заметок нет, собирать нечего."
            )
            continue

        note = await message.answer(f"⏳ {student['full_name']}…")
        try:
            group_notes = await db.group_answers(student["group_id"])
            mentors = await db.group_mentors(student["group_id"])
            data = await llm.generate(student, answers, group_notes)

            html_path = render.render_html(
                student, data,
                mentors=", ".join(m["full_name"].split()[0] for m in mentors),
                duration=f"{len(COURSE['days']) - 1} занятий, 2 недели + финальный хакатон",
            )
            await db.save_characteristic(sid, data, str(html_path))

            pdf = render.try_pdf(html_path)
            doc = pdf or html_path
            caption = f"🧪 черновик · {student['full_name']}"
            if not pdf:
                caption += "\nHTML — откроется в браузере, оттуда «Печать → Сохранить как PDF»."
            if data.get("_error"):
                caption += f"\n⚠️ LLM не ответил ({data['_error']}), это черновик."
            await note.delete()
            await message.answer_document(FSInputFile(doc), caption=caption)
        except Exception as e:  # noqa: BLE001
            log.exception("Не собралась характеристика для %s", student["full_name"])
            await note.edit_text(f"❌ {student['full_name']}: {e}")
        await asyncio.sleep(0.3)  # не долбим Telegram лимитами
