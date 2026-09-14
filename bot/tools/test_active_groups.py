"""Проверка «скрытия» завершённых групп без Telegram: python -m tools.test_active_groups

Группа считается завершённой, когда конец последнего дня курса
(db.LAST_DAY_INDEX, сейчас день 9 — хакатон) уже в прошлом (db._group_finished).
db.groups()/db.mentor_groups() по умолчанию (active_only=True) отдают только
незавершённые — и группы без start_date (ещё не начаты).

Что проверяем:
  1. группа с давним стартом (день 9 давно прошёл) не попадает в db.groups();
  2. группа с будущим стартом (день 9 ещё не наступил) попадает;
  3. группа без start_date попадает (ещё не начата — не значит завершена);
  4. db.groups(active_only=False) видит вообще все группы, включая завершённые;
  5. то же самое для db.mentor_groups() — ментор видит только свои активные группы.
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
from app import db  # noqa: E402
from app.config import settings  # noqa: E402


async def main() -> None:
    await pgtest.prepare()
    await db.init()
    all_ok = True

    today = dt.datetime.now(settings.tz).date()
    # День 9 (хакатон) — offset_days у него 13 (см. course.yaml), длительность
    # 180 минут. С запасом: старт 60 дней назад железно завершён, старт через
    # 60 дней железно ещё не начался.
    far_past = (today - dt.timedelta(days=60)).isoformat()
    near_future = (today + dt.timedelta(days=60)).isoformat()

    finished_gid = await db.upsert_group("Завершённая группа", far_past, shift="evening")
    upcoming_gid = await db.upsert_group("Будущая группа", near_future, shift="evening")
    undated_gid = await db.upsert_group("Группа без даты")

    print("--- db._group_finished напрямую ---")
    g_finished = await db.group(finished_gid)
    g_upcoming = await db.group(upcoming_gid)
    g_undated = await db.group(undated_gid)

    ok = await db._group_finished(g_finished) is True
    print(f"  группа с давним стартом -> завершена: {ok}")
    all_ok &= ok

    ok = await db._group_finished(g_upcoming) is False
    print(f"  группа с будущим стартом -> НЕ завершена: {ok}")
    all_ok &= ok

    ok = await db._group_finished(g_undated) is False
    print(f"  группа без start_date -> НЕ завершена (ещё не начата): {ok}")
    all_ok &= ok

    print("\n--- db.groups() (active_only=True по умолчанию) ---")
    active = await db.groups()
    active_ids = {g["id"] for g in active}

    ok = finished_gid not in active_ids
    print(f"  завершённая группа НЕ в списке активных: {ok}")
    all_ok &= ok

    ok = upcoming_gid in active_ids
    print(f"  группа с будущим стартом — в списке активных: {ok}")
    all_ok &= ok

    ok = undated_gid in active_ids
    print(f"  группа без даты — в списке активных: {ok}")
    all_ok &= ok

    print("\n--- db.groups(active_only=False) — вообще все ---")
    everything = await db.groups(active_only=False)
    everything_ids = {g["id"] for g in everything}
    ok = {finished_gid, upcoming_gid, undated_gid} <= everything_ids
    print(f"  все три группы на месте, включая завершённую: {ok}")
    all_ok &= ok

    print("\n--- db.mentor_groups(): ментор видит только свои активные ---")
    mid = await db.register_mentor(555, "+77019990000", "Тестовый Ментор")
    for gid in (finished_gid, upcoming_gid, undated_gid):
        await db.link_mentor_group(mid, gid)

    mentor_active = await db.mentor_groups(mid)
    mentor_active_ids = {g["id"] for g in mentor_active}
    ok = finished_gid not in mentor_active_ids
    print(f"  ментор не видит завершённую группу среди своих активных: {ok}")
    all_ok &= ok
    ok = {upcoming_gid, undated_gid} <= mentor_active_ids
    print(f"  но видит будущую и без даты: {ok}")
    all_ok &= ok

    mentor_all = await db.mentor_groups(mid, active_only=False)
    mentor_all_ids = {g["id"] for g in mentor_all}
    ok = finished_gid in mentor_all_ids
    print(f"  active_only=False — и завершённая группа тоже видна: {ok}")
    all_ok &= ok

    await db.close()
    print("\n" + ("ВСЁ ОК" if all_ok else "ЕСТЬ ОШИБКИ"))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
