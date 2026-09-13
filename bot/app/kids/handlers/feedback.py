"""Отзыв об уроке. Анонимно по политике: student_id пишется в базу для
дедупликации («уже отвечал сегодня»), но ни один экран для менторов/админа
не показывает имя рядом с текстом — см. db.group_kid_feedback().
"""
from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app import db, stt
from app.config import COURSE, settings
from app.kids import keyboards as kb

log = logging.getLogger(__name__)
router = Router(name="kids-feedback")


class Feedback(StatesGroup):
    rating = State()
    comment = State()


async def _current_day(group_id: int) -> int | None:
    """Последний день курса, занятие по которому уже началось — к нему и
    привязываем отзыв. Отзыва «про будущее» не бывает."""
    now = dt.datetime.now(settings.tz)
    best = None
    for d in COURSE["days"]:
        window = await db.group_lesson_window(group_id, d["index"])
        if window and window[0] <= now:
            if best is None or int(d["index"]) > best:
                best = int(d["index"])
    return best


@router.message(F.text == "💬 Отзыв об уроке")
@router.message(Command("feedback"))
async def feedback_entry(message: Message, state: FSMContext) -> None:
    await state.clear()
    student = await db.student_by_tg(message.from_user.id)
    if not student:
        await message.answer("Сначала зарегистрируйся: /start")
        return

    day = await _current_day(student["group_id"])
    if day is None:
        await message.answer("Занятия ещё не начались — писать пока не о чем.")
        return

    already = await db.kid_feedback_done(student["id"], day)
    # student_id кладём в состояние сразу: дальше отзыв идёт через инлайн-кнопки
    # (call.message — это сообщение БОТА, а не ученика, из него личность не
    # достать), поэтому кому сохранять отзыв решаем один раз здесь, а не по
    # ходу — так не перепутаем автора с ботом.
    await state.update_data(student_id=student["id"], group_id=student["group_id"],
                            day_index=day)
    await state.set_state(Feedback.rating)
    title = COURSE["days"][day - 1]["title"] if 1 <= day <= len(COURSE["days"]) else f"день {day}"
    prefix = "Ты уже отвечал за этот урок — можно переписать.\n\n" if already else ""
    await message.answer(
        f"{prefix}Как прошёл урок «{title}»?\n"
        "Наставник увидит оценку и текст, но не твоё имя.",
        reply_markup=kb.rating(),
    )


@router.callback_query(F.data.startswith("fb:rate:"), Feedback.rating)
async def got_rating(call: CallbackQuery, state: FSMContext) -> None:
    value = int(call.data.split(":")[2])
    await state.update_data(rating=value)
    await state.set_state(Feedback.comment)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer(f"{value}⭐")
    await call.message.answer(
        "Хочешь добавить пару слов — что понравилось, что нет? "
        "Текстом или голосом, необязательно.",
        reply_markup=kb.feedback_skip_comment(),
    )


@router.callback_query(F.data == "fb:skip", Feedback.comment)
async def skip_comment(call: CallbackQuery, state: FSMContext) -> None:
    await _finish(state, None, "text")
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer()
    await call.message.answer("Спасибо! Отзыв ушёл наставнику без твоего имени.")


@router.message(Feedback.comment, F.text)
async def text_comment(message: Message, state: FSMContext) -> None:
    if message.text.strip().startswith("/"):
        await message.answer("Ещё жду отзыв — можно текстом, голосом или «Без комментария».")
        return
    await _finish(state, message.text.strip(), "text")
    await message.answer("Спасибо! Отзыв ушёл наставнику без твоего имени.")


@router.message(Feedback.comment, F.voice | F.audio)
async def voice_comment(message: Message, state: FSMContext, bot: Bot) -> None:
    note = await message.answer("🎙 Расшифровываю…")
    voice = message.voice or message.audio
    path = Path(settings.media_dir) / f"kid_{message.chat.id}_{message.message_id}.oga"
    try:
        await bot.download(voice.file_id, destination=str(path))
        tr = await stt.transcribe(path)
    except stt.STTUnavailable as e:
        await note.edit_text(f"Не смог расшифровать: {e}\nНапиши текстом, пожалуйста.")
        return
    except Exception:
        log.exception("Ошибка расшифровки отзыва")
        await note.edit_text("Расшифровка сорвалась. Напиши текстом, пожалуйста.")
        return
    finally:
        path.unlink(missing_ok=True)

    if not tr:
        await note.edit_text("В записи ничего не разобрал. Попробуй ещё раз или текстом.")
        return
    await note.delete()
    await _finish(state, tr.text, "voice")
    await message.answer("Спасибо! Отзыв ушёл наставнику без твоего имени.")


@router.message(Command("stop"), Feedback.rating)
@router.message(Command("stop"), Feedback.comment)
async def stop_feedback(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Ок, отменил. Захочешь оставить отзыв — /feedback.")


async def _finish(state: FSMContext, text: str | None, source: str) -> None:
    data = await state.get_data()
    await db.save_kid_feedback(
        student_id=data["student_id"], group_id=data["group_id"],
        day_index=data["day_index"], rating=data.get("rating"),
        text=text, source=source,
    )
    await state.clear()
