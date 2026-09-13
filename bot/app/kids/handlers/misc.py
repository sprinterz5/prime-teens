"""Расписание своей группы и справка."""
from __future__ import annotations

import datetime as dt

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app import db
from app.config import COURSE, settings

router = Router(name="kids-misc")

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


async def _my_student(message: Message):
    student = await db.student_by_tg(message.from_user.id)
    if not student:
        await message.answer("Сначала зарегистрируйся: /start")
    return student


@router.message(F.text == "🗓 Расписание")
@router.message(Command("schedule"))
async def schedule(message: Message) -> None:
    student = await _my_student(message)
    if not student:
        return
    group = await db.group(student["group_id"])
    if not group or not group["start_date"]:
        await message.answer("Расписание группы ещё не готово — спроси наставника.")
        return

    now = dt.datetime.now(settings.tz)
    lines = [f"<b>{group['name']}</b>"]
    for d in COURSE["days"]:
        window = await db.group_lesson_window(group["id"], d["index"])
        if window is None:
            continue
        when, end = window
        mark = "▶️" if when.date() == now.date() else ("· " if when > now else "✅")
        lines.append(
            f"{mark} <b>День {d['index']}</b> · {WEEKDAYS[when.weekday()]} "
            f"{when.strftime('%d.%m')} {when.strftime('%H:%M')}–{end.strftime('%H:%M')} "
            f"— {d['title']}"
        )
        if d.get("homework"):
            lines.append(f"      домашка: {d['homework']}")
    lines.append("\n▶️ сегодня · ✅ прошло · · предстоит")
    await message.answer("\n".join(lines))


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await message.answer(
        "<b>Что я умею</b>\n\n"
        "/start — регистрация по номеру\n"
        "/schedule — расписание твоей группы\n"
        "/feedback — отзыв об уроке (наставник не видит, кто написал)\n"
        "/team — команда на хакатон\n"
        "/whoami — мой Telegram ID"
    )
