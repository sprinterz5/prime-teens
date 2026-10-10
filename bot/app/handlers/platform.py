"""Вход на веб-платформу: кабинет ментора (прогресс тетрадей, проверка
домашки) живёт там, бот выдаёт одноразовую ссылку/код (см. app/platform.py)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app import db, platform

router = Router(name="platform")

BUTTON = "💻 Платформа"


@router.message(F.text == BUTTON)
@router.message(Command("login"))
async def login(message: Message) -> None:
    mentor = await db.mentor_by_tg(message.from_user.id)
    if not mentor:
        await message.answer("Сначала зарегистрируйся: /start")
        return
    text, markup = await platform.login_message(
        "mentor", message.from_user.id, mentor_id=mentor["id"],
    )
    await message.answer(text, reply_markup=markup, disable_web_page_preview=True)
