"""Напоминания для учеников: один тик раз в 5 минут, тот же приём, что у
ментора (app/scheduler.py) — тик сам решает, что уже пора, и не шлёт
дважды (таблица notifications, общая с ментором, но ключи с префиксом
kid: — чтобы дедупликация двух ботов не пересекалась).
"""
from __future__ import annotations

import datetime as dt
import html
import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app import db, platform
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
    await notify_homework_reviews(bot)
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
                        f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}\n{block_lines}"
                        + platform.link_line("Задания дня", f"/course/day/{day}"),
                    )

            # --- после занятия: домашка и отзыв (по одной попытке, без давления) ---
            if d.get("hackathon"):
                continue  # про хакатон отдельного отзыва не просим
            fire = end + dt.timedelta(minutes=int(rem["checklist_after_min"]))
            if not _due(now, fire, FRESH_FEEDBACK):
                continue
            if (d.get("homework") or "").strip() and settings.platform_url:
                for s in students:
                    if await db.homework_submitted(s["id"], day):
                        continue
                    if not await db.mark_sent(f"kidhw:{s['id']}:{day}"):
                        continue
                    await _send(
                        bot, s["tg_user_id"],
                        f"📚 Домашка к следующему занятию: {d['homework']}"
                        + platform.link_line("Сдать на платформе", f"/course/day/{day}"),
                    )
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


async def notify_homework_reviews(bot: Bot) -> None:
    """Ментор проверил домашку на платформе — сообщаем ученику. Сама
    отметка notified_at в таблице homework и служит дедупликацией."""
    try:
        rows = await db.homework_reviews_to_notify()
    except Exception:
        log.exception("Тик: не смог прочитать проверенную домашку")
        return
    titles = {int(d["index"]): d["title"] for d in COURSE["days"]}
    for h in rows:
        day = int(h["day_index"])
        title = titles.get(day, f"день {day}")
        if h["status"] == "accepted":
            text = f"✅ Наставник принял домашку к уроку «{title}»."
        else:
            text = f"↩️ Наставник вернул домашку к уроку «{title}» на доработку."
        if h["mentor_comment"]:
            text += f"\nКомментарий: {html.escape(h['mentor_comment'])}"
        text += platform.link_line("Открыть", f"/course/day/{day}")
        await _send(bot, h["tg_user_id"], text)
        await db.mark_homework_notified(h["student_id"], day, h["reviewed_at"])


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
