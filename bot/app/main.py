"""Точка входа. Long polling — вебхук/белый IP не нужны."""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app import db, scheduler
from app.config import settings
from app.handlers import build_router

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
log = logging.getLogger("primeteens")

COMMANDS = [
    BotCommand(command="start", description="Регистрация / главное меню"),
    BotCommand(command="checklist", description="Заполнить чек-лист после занятия"),
    BotCommand(command="final", description="Финальный опрос перед характеристиками"),
    BotCommand(command="export", description="Выгрузить материалы для характеристик"),
    BotCommand(command="feedback", description="Отзывы учеников (без имён)"),
    BotCommand(command="schedule", description="Расписание группы"),
    BotCommand(command="group", description="Состав группы"),
    BotCommand(command="stop", description="Прервать чек-лист"),
    BotCommand(command="help", description="Справка"),
]


async def main() -> None:
    if not settings.bot_token:
        log.error("BOT_TOKEN пуст. Скопируй .env.example в .env и впиши токен.")
        return

    await db.init()
    bot = Bot(settings.bot_token,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(build_router())

    commands = list(COMMANDS)
    if settings.experimental_characteristics:
        commands.insert(4, BotCommand(command="characteristics",
                                      description="🧪 Черновик характеристик моделью"))

    me = await bot.get_me()
    await bot.set_my_commands(commands)
    log.info("Бот @%s запущен. TZ=%s, STT=%s, LLM=%s",
             me.username, settings.tz_name, settings.stt_provider, settings.llm_provider)

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
