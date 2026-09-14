"""Напоминания для учеников: один тик раз в 5 минут, тот же приём, что у
ментора (app/scheduler.py) — тик сам решает, что уже пора, и не шлёт
дважды (таблица notifications, общая с ментором, но ключи с префиксом
kid: — чтобы дедупликация двух ботов не пересекалась).
"""
from __future__ import annotations

import datetime as dt
import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app import db
from app.config import COURSE, settings

log = logging.getLogger(__name__)

TICK_MINUTES = 5
FRESH_PRE = dt.timedelta(hours=2)
FRESH_FEEDBACK = dt.timedelta(hours=10)


def _due(now: dt.datetime, fire_at: dt.datetime, freshness: dt.timedelta) -> bool:
    return fire_at <= now < fire_at + freshness


async def _linked_students(group_id: int) -> list:
    return await db.q(
        "SELECT * FROM students WHERE group_id = ? AND active AND tg_user_id IS NOT NULL",
        group_id,
    )


async def tick(bot: Bot) -> None:
    now = dt.datetime.now(settings.tz)
    try:
        groups = await db.groups()  # только активные (см. db.groups active_only=True)
    except Exception:
        log.exception("Тик: не смог прочитать группы")
        return

    rem = COURSE["reminders"]

    for g in groups:
        students = await _linked_students(g["id"])
        if not students:
            continue

        for d in COURSE["days"]:
            day = int(d["index"])
            window = await db.group_lesson_window(g["id"], day)
            if window is None:
                continue
            start, end = window

            # --- до занятия ---
            for minutes in rem["before_lesson_min"]:
                fire = start - dt.timedelta(minutes=int(minutes))
                if not _due(now, fire, FRESH_PRE):
                    continue
                block_lines = "\n".join(
                    "  " + db.fmt_block(t0, t1, name)
                    for t0, t1, name in db.day_block_times(d, start)
                )
                for s in students:
                    key = f"kidpre:{s['id']}:{day}:{minutes}"
                    if not await db.mark_sent(key):
                        continue
                    await _send(
                        bot, s["tg_user_id"],
                        f"⏰ Через {minutes} мин занятие «{d['title']}»\n"
                        f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}\n{block_lines}",
                    )

            # --- после занятия: попросить отзыв (одна попытка, без давления) ---
            if d.get("hackathon"):
                continue  # про хакатон отдельного отзыва не просим
            fire = end + dt.timedelta(minutes=int(rem["checklist_after_min"]))
            if not _due(now, fire, FRESH_FEEDBACK):
                continue
            for s in students:
                if await db.kid_feedback_done(s["id"], day):
                    continue
                key = f"kidfb:{s['id']}:{day}"
                if not await db.mark_sent(key):
                    continue
                await _send(
                    bot, s["tg_user_id"],
                    f"Как прошёл урок «{d['title']}»? Пара слов наставнику "
                    "(без твоего имени) — /feedback",
                )


async def _send(bot: Bot, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text)
    except Exception:
        log.warning("Не доставил сообщение %s", chat_id, exc_info=True)


def setup(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.tz)
    scheduler.add_job(
        tick, "interval", minutes=TICK_MINUTES, args=[bot],
        id="kid-reminders", max_instances=1, coalesce=True, misfire_grace_time=300,
    )
    scheduler.start()
    return scheduler
