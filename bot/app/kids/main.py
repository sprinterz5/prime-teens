"""Точка входа детского бота. Отдельный процесс, та же БД, что у ментора
(app/db.py — общий модуль, SQLite в WAL-режиме спокойно переживает два
процесса-клиента). Long polling, как и у ментора — вебхук/белый IP не нужны.
"""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app import db
from app.config import settings
from app.kids import scheduler
from app.kids.handlers import build_router

# Windows-консоль по умолчанию cp1251 — кириллица в логах иначе роняет процесс
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("primeteens.kids")

COMMANDS = [
    BotCommand(command="start", description="Регистрация по номеру"),
    BotCommand(command="schedule", description="Расписание группы"),
    BotCommand(command="feedback", description="Отзыв об уроке"),
    BotCommand(command="team", description="Команда на хакатон"),
    BotCommand(command="join", description="Вступить в команду по коду"),
    BotCommand(command="whoami", description="Мой Telegram ID"),
    BotCommand(command="help", description="Справка"),
]


async def main() -> None:
    if not settings.kids_bot_token:
        log.error("KIDS_BOT_TOKEN пуст. Впиши токен в .env, чтобы запустить детского бота.")
        return

    await db.init()
    bot = Bot(settings.kids_bot_token,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(build_router())

    me = await bot.get_me()
    await bot.set_my_commands(COMMANDS)
    log.info("Детский бот @%s запущен. TZ=%s, STT=%s", me.username, settings.tz_name,
             settings.stt_provider)
    if not settings.kids_bot_username:
        log.warning(
            "KIDS_BOT_USERNAME пуст в .env — заполни его (%s), иначе ссылки на "
            "команды хакатона (t.me/<бот>?start=team_<код>) не соберутся.",
            me.username,
        )
    elif settings.kids_bot_username != me.username:
        log.warning(
            "KIDS_BOT_USERNAME в .env (%s) не совпадает с реальным именем этого "
            "бота (%s) — ссылки будут вести не туда. Поправь .env.",
            settings.kids_bot_username, me.username,
        )

    sched = scheduler.setup(bot)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        sched.shutdown(wait=False)
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Остановлен.")
