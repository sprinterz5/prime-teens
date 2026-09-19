"""Проверка автоматической архивации потока без Telegram: python -m tools.test_archive_lock

scheduler.archive_lock — тик раз в 5 минут (см. app/scheduler.py), который
запирает группу («Завершить поток»), когда её курс уже закончился
(db._group_finished — единый источник истины про расписание). Что проверяем:

  1. группа с давним стартом (хакатон точно прошёл), ещё не запертая и не
     отпертая вручную -> archived_at выставляется, ends_at = конец хакатона;
  2. группа, которую админ уже отпер вручную (archive_reopened=true) —
     archive_lock её НЕ трогает, даже если курс формально закончился;
  3. группа с будущим стартом (курс ещё не шёл) — archived_at остаётся NULL,
     но ends_at всё равно считается (дашборд показывает «закроется…»);
  4. группа без start_date — ничего не считаем, ends_at остаётся NULL;
  5. уже запертая группа (archived_at уже стоит) — тик её не трогает повторно
     (archived_at не меняется).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools._pgtest import TEST_DATABASE_URL  # noqa: E402

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from tools import _pgtest as pgtest  # noqa: E402
from app import db, scheduler  # noqa: E402
from app.config import settings  # noqa: E402


async def main() -> None:
    await pgtest.prepare()
    await db.init()
    all_ok = True

    today = dt.datetime.now(settings.tz).date()
    far_past = (today - dt.timedelta(days=60)).isoformat()
    near_future = (today + dt.timedelta(days=60)).isoformat()

    finished_gid = await db.upsert_group("Группа для архивации", far_past, shift="evening")
    reopened_gid = await db.upsert_group("Отпертая группа", far_past, shift="evening")
    upcoming_gid = await db.upsert_group("Будущая группа", near_future, shift="evening")
    undated_gid = await db.upsert_group("Группа без даты")
    already_archived_gid = await db.upsert_group("Уже запертая группа", far_past, shift="evening")

    await db.run("UPDATE groups SET archive_reopened = true WHERE id = ?", reopened_gid)
    manual_archived_at = dt.datetime.now(settings.tz) - dt.timedelta(days=1)
    await db.run("UPDATE groups SET archived_at = ? WHERE id = ?", manual_archived_at, already_archived_gid)

    # По студенту в каждой из групп, что должны запираться — проверяем, что
    # archive_lock не падает на рассылке уведомлений (реальных Telegram-
    # получателей тут нет, только pg_notify — слушателя в этом тесте тоже
    # нет, но вызов не должен бросать исключение).
    await db.q1(
        "INSERT INTO students (group_id, full_name, active) VALUES (?, ?, true) RETURNING id",
        finished_gid, "Тестовый Ученик",
    )

    await scheduler.archive_lock()

    print("--- запертая по расписанию группа ---")
    g = await db.group(finished_gid)
    ok = g["archived_at"] is not None
    print(f"  archived_at выставлен: {ok}")
    all_ok &= ok
    ok = g["ends_at"] is not None
    print(f"  ends_at выставлен: {ok}")
    all_ok &= ok

    print("\n--- вручную отпертая группа (archive_reopened=true) ---")
    g = await db.group(reopened_gid)
    ok = g["archived_at"] is None
    print(f"  archived_at остаётся NULL несмотря на прошедший курс: {ok}")
    all_ok &= ok
    ok = g["ends_at"] is not None
    print(f"  ends_at всё равно посчитан: {ok}")
    all_ok &= ok

    print("\n--- группа с будущим стартом ---")
    g = await db.group(upcoming_gid)
    ok = g["archived_at"] is None
    print(f"  archived_at остаётся NULL: {ok}")
    all_ok &= ok
    ok = g["ends_at"] is not None
    print(f"  ends_at посчитан (для подсказки в дашборде): {ok}")
    all_ok &= ok

    print("\n--- группа без start_date ---")
    g = await db.group(undated_gid)
    ok = g["archived_at"] is None and g["ends_at"] is None
    print(f"  archived_at и ends_at остаются NULL: {ok}")
    all_ok &= ok

    print("\n--- уже запертая вручную группа ---")
    g = await db.group(already_archived_gid)
    ok = g["archived_at"] is not None and abs((g["archived_at"] - manual_archived_at).total_seconds()) < 1
    print(f"  archived_at не переписан повторным тиком: {ok}")
    all_ok &= ok

    await db.close()
    print("\n" + ("ВСЁ ОК" if all_ok else "ЕСТЬ ОШИБКИ"))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
