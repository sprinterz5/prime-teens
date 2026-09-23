"""Напоминания.

Реализовано одним тиком раз в 5 минут вместо сотен персональных задач:
тик проходит по парам «ментор × группа», считает, что должно было сработать,
и отправляет то, что ещё не отправлялось (таблица notifications = защита от
дублей и от «догоняющих» рассылок после перезапуска).

Стоимость тика — несколько SELECT'ов по SQLite. На фоне этого сам факт
работы бота заметнее, чем планировщик.
"""
from __future__ import annotations

import datetime as dt
import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app import db, flow, keyboards as kb
from app.config import COURSE, settings

log = logging.getLogger(__name__)

TICK_MINUTES = 5
# Насколько поздно ещё имеет смысл отправить просроченное напоминание
FRESH_PRE = dt.timedelta(hours=2)
FRESH_CHECKLIST = dt.timedelta(hours=14)


def _due(now: dt.datetime, fire_at: dt.datetime, freshness: dt.timedelta) -> bool:
    return fire_at <= now < fire_at + freshness


async def tick(bot: Bot) -> None:
    now = dt.datetime.now(settings.tz)
    try:
        pairs = await db.all_mentor_group_pairs()
    except Exception:
        log.exception("Тик: не смог прочитать пары ментор/группа")
        return

    rem = COURSE["reminders"]

    for p in pairs:
        gid = p["group_id"]
        for d in COURSE["days"]:
            day = int(d["index"])
            window = await db.group_lesson_window(gid, day)
            if window is None:
                continue
            start, end = window
            hackathon = bool(d.get("hackathon"))

            # --- до занятия ---
            for minutes in rem["before_lesson_min"]:
                fire = start - dt.timedelta(minutes=int(minutes))
                if not _due(now, fire, FRESH_PRE):
                    continue
                key = f"pre:{p['mentor_id']}:{gid}:{day}:{minutes}"
                if not await db.mark_sent(key):
                    continue
                block_lines = "\n".join(
                    "  " + db.fmt_block(t0, t1, name)
                    for t0, t1, name in db.day_block_times(d, start)
                )
                tail = ""
                if d.get("tasks"):
                    tail += f"\nЗадания: {' · '.join(d['tasks'])}"
                if d.get("homework"):
                    tail += f"\nДомашка к следующему: {d['homework']}"
                await _send(
                    bot, p["tg_user_id"],
                    f"⏰ Через {minutes} мин занятие у группы <b>{p['group_name']}</b>\n"
                    f"<b>День {day} · {d['weekday']}, "
                    f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}</b>\n"
                    f"{block_lines}{tail}",
                )

            # --- после занятия: чек-лист (в день хакатона — свой опрос) ---
            if d.get("post_lesson_checklist") is False and not hackathon:
                continue
            kind = "hackathon" if hackathon else "lesson"
            fire = end + dt.timedelta(minutes=int(rem["checklist_after_min"]))
            attempts = [(fire, f"ck:{p['mentor_id']}:{gid}:{day}")] + [
                (end + dt.timedelta(hours=int(h)), f"nudge:{p['mentor_id']}:{gid}:{day}:{h}")
                for h in rem["checklist_nudge_hours"]
            ]
            for fire_at, key in attempts:
                if not _due(now, fire_at, FRESH_CHECKLIST):
                    continue
                if await db.mentor_session_closed(p["mentor_id"], gid, day, kind):
                    break
                if not await db.mark_sent(key):
                    continue
                again = key.startswith("nudge")
                if hackathon:
                    text = (
                        ("🔔 Опрос по хакатону за день "
                         if again else "Хакатон закончился. Пройдёмся по опросу за день ")
                        + f"<b>{day}</b>, группа {p['group_name']}?\n\n"
                          "Как выступили команды на защите, кто был в ударе."
                    )
                else:
                    text = (
                        ("🔔 Опрос за день "
                         if again else "Занятие закончилось. Пройдёмся по опросу за день ")
                        + f"<b>{day} — {d['title']}</b>, группа {p['group_name']}?\n\n"
                          "Только про тех, кого отметишь: кто отличился, у кого не шло, "
                          "кого не было. Плюс двое под прожектором. Голосовыми — 3–4 минуты."
                    )
                await _send(bot, p["tg_user_id"], text, markup=kb.start_checklist(gid, day, kind))

        # --- финальный опрос перед характеристиками ---
        after_day = int(COURSE["characteristics"]["after_day"])
        last = await db.group_lesson_datetime(gid, after_day)
        if last is None:
            continue
        hh, mm = COURSE["characteristics"]["remind_at"].split(":")
        fire = last.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
        if _due(now, fire, dt.timedelta(hours=36)) and not await db.session_done(gid, 0, "final"):
            key = f"final:{p['mentor_id']}:{gid}"
            if await db.mark_sent(key):
                await _send(
                    bot, p["tg_user_id"],
                    "🏁 Курс и хакатон позади.\n\n"
                    "Пора собрать характеристики. Финальный опрос: по каждому ученику "
                    "5–6 вопросов (сильные стороны, было → стало, зона роста, куда дальше). "
                    "Голосовыми — минут 15 на группу.",
                    markup=kb.start_checklist(gid, 0, "final"),
                )


async def digest(bot: Bot) -> None:
    """Воскресный дайджест: по кому эпизодов нет.

    Смысл в одном — успеть заметить пустого ученика, пока курс идёт, а не
    когда сел писать характеристику и обнаружил, что писать нечего.
    """
    cfg = COURSE.get("digest") or {}
    now = dt.datetime.now(settings.tz)
    if now.weekday() != int(cfg.get("weekday", 6)):
        return
    hh, mm = str(cfg.get("at", "12:00")).split(":")
    fire = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    if not _due(now, fire, dt.timedelta(hours=6)):
        return

    for p in await db.all_mentor_group_pairs():
        gid = p["group_id"]
        key = f"digest:{p['mentor_id']}:{gid}:{now.date()}"
        if not await db.mark_sent(key):
            continue

        students = await db.students(gid)
        if not students:
            continue
        counts = await db.episode_counts(gid)
        done = [d["index"] for d in COURSE["days"]
                if await db.session_done(gid, int(d["index"]))]
        total_eps = sum(counts.values())

        good = [s for s in students if counts.get(s["id"], 0) >= 2]
        few = [s for s in students if counts.get(s["id"], 0) == 1]
        zero = [s for s in students if counts.get(s["id"], 0) == 0]

        def names(rows):
            return ", ".join(r["short_name"] or r["full_name"] for r in rows)

        lines = [
            f"📊 <b>{p['group_name']}</b> · занятий заполнено {len(done)} · "
            f"эпизодов {total_eps}",
        ]
        if good:
            lines.append(f"🟢 Достаточно: {names(good)}")
        if few:
            lines.append(f"🟡 Маловато: {names(few)}")
        if zero:
            lines.append(f"🔴 Пусто: {names(zero)}")
            nxt = flow.pick_spotlight(students, counts, await db.spotlight_counts(gid))
            lines.append(f"\nНа следующем занятии прожектор встанет на "
                         f"<b>{names(nxt)}</b> — по ним спрошу подробнее.")
        else:
            lines.append("\nПустых нет — материала хватит на всех.")
        await _send(bot, p["tg_user_id"], "\n".join(lines))


async def sheet_sync(bot: Bot) -> None:
    """Ночной автозабор Google-таблицы — см. app/handlers/admin.py:pull_sheet
    и integrations/sheets_sync.gs. Бот САМ ходит по ссылке (SHEETS_SYNC_URL);
    ничего не настроено — молча ничего не делаем, а не падаем."""
    if not settings.sheets_sync_url:
        return
    now = dt.datetime.now(settings.tz)
    fire = now.replace(hour=settings.sheets_sync_hour, minute=0, second=0, microsecond=0)
    if not _due(now, fire, dt.timedelta(hours=1)):
        return
    key = f"sheetsync:{now.date()}"
    if not await db.mark_sent(key):
        return

    from app.handlers.admin import _format_import_report, pull_sheet  # noqa: PLC0415
    report = await pull_sheet()
    for admin_id in settings.admin_ids:
        if report.get("_fatal"):
            await _send(bot, admin_id, f"🌙 Ночная синхронизация с таблицей не удалась: "
                                       f"{report['_fatal']}")
            continue
        for line in _format_import_report(
                report, title="🌙 Ночная синхронизация с Google-таблицей."):
            await _send(bot, admin_id, line)


ARCHIVE_TICK_MINUTES = 5
# «Через сколько после конца хакатона реально запирать тетради» — сейчас 0
# (запираем ровно в момент конца), константа отдельно от db._group_finished,
# чтобы при необходимости завести отступ без переписывания остальной логики.
ARCHIVE_GRACE_MINUTES = 0


async def archive_lock() -> None:
    """«Завершить поток» — автоматически, без участия админа.

    Раз в ARCHIVE_TICK_MINUTES проходит по всем группам:
      - обновляет groups.ends_at (конец последнего дня курса — хакатона,
        db.LAST_DAY_INDEX) — на него смотрит дашборд ментора, показывая
        «Тетради закроются после хакатона, …», пока группа ещё не заперта;
      - группе, где курс уже закончился (db._group_finished — ЕДИНЫЙ
        источник истины про расписание, схему заново не считаем) и которую
        админ не отпирал вручную (archive_reopened=false) и которая ещё не
        заперта (archived_at IS NULL), выставляет archived_at и уведомляет
        каждого её ученика через pg_notify('workbook', …) — см.
        db.notify_workbook — чтобы открытая вкладка тетради переключилась в
        режим «только чтение» не дожидаясь перезагрузки страницы.

    Сжатие рисунков в WebP и выгрузка PDF сюда намеренно не входят — это
    отдельный, более тяжёлый процесс на стороне Next.js
    (pnpm archive:pending, см. scripts/archive-pending.ts), бот его не
    запускает и не ждёт."""
    now = dt.datetime.now(settings.tz)
    try:
        rows = await db.q("SELECT * FROM groups")
    except Exception:
        log.exception("archive_lock: не смог прочитать группы")
        return

    for g in rows:
        if not g["start_date"]:
            continue
        try:
            window = await db.group_lesson_window(g["id"], db.LAST_DAY_INDEX)
        except Exception:
            log.exception("archive_lock: не смог посчитать окно занятия для группы %s", g["id"])
            continue
        if window is None:
            continue
        end = window[1] + dt.timedelta(minutes=ARCHIVE_GRACE_MINUTES)

        if g["ends_at"] != end:
            await db.run("UPDATE groups SET ends_at = ? WHERE id = ?", end, g["id"])

        if g["archived_at"] is not None or g["archive_reopened"]:
            continue
        if not await db._group_finished(g):
            continue
        if now < end:
            continue

        await db.run("UPDATE groups SET archived_at = ? WHERE id = ?", end, g["id"])
        log.info("archive_lock: группа %s (%s) заперта, конец хакатона %s", g["id"], g["name"], end)
        try:
            group_students = await db.students(g["id"])
            for s in group_students:
                await db.notify_workbook({
                    "kind": "archive_changed",
                    "studentId": s["id"],
                    "groupId": g["id"],
                    "archived": True,
                    "updatedAt": end.isoformat(),
                })
        except Exception:
            log.exception("archive_lock: заперли группу %s, но не смог уведомить веб (pg_notify)", g["id"])


async def _send(bot: Bot, chat_id: int, text: str, markup=None) -> None:
    try:
        await bot.send_message(chat_id, text, reply_markup=markup)
    except Exception:
        log.warning("Не доставил сообщение %s", chat_id, exc_info=True)


def setup(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.tz)
    scheduler.add_job(
        tick, "interval", minutes=TICK_MINUTES, args=[bot],
        id="reminders", max_instances=1, coalesce=True, misfire_grace_time=300,
    )
    scheduler.add_job(
        digest, "interval", minutes=30, args=[bot],
        id="digest", max_instances=1, coalesce=True, misfire_grace_time=1800,
    )
    scheduler.add_job(
        sheet_sync, "interval", minutes=30, args=[bot],
        id="sheet-sync", max_instances=1, coalesce=True, misfire_grace_time=1800,
    )
    scheduler.add_job(
        archive_lock, "interval", minutes=ARCHIVE_TICK_MINUTES,
        id="archive-lock", max_instances=1, coalesce=True, misfire_grace_time=300,
    )
    scheduler.start()
    return scheduler
