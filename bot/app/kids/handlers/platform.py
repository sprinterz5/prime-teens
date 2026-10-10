"""Вход на веб-платформу: тетрадь по дням и домашка живут там, бот выдаёт
одноразовую ссылку/код (см. app/platform.py)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app import db, platform

router = Router(name="kids-platform")

BUTTON = "💻 Тетрадь и домашка"


@router.message(F.text == BUTTON)
@router.message(Command("login"))
async def login(message: Message) -> None:
    student = await db.student_by_tg(message.from_user.id)
    if not student or not student["active"]:
        await message.answer("Сначала зарегистрируйся: /start")
        return
    text, markup = await platform.login_message(
        "student", message.from_user.id, student_id=student["id"],
    )
    await message.answer(text, reply_markup=markup, disable_web_page_preview=True)
