"""Проверка связки ботов с веб-платформой без Telegram: python -m tools.test_platform

Что проверяем:
  1. /login: issue_login_code хранит только sha256 ссылки, код — 6 цифр,
     срок жизни — LOGIN_TTL_MINUTES, а новая выдача гасит прежние
     неиспользованные коды того же человека (и только его).
  2. Домашка: проверенную ментором сдачу детский бот видит ровно один раз;
     если ментор перепроверил, пока уходило сообщение, отметка
     notified_at старую проверку не закрывает.
  3. Курс-директор: выдаётся по номеру до и после /start, повторная
     регистрация и Excel-импорт роль не снимают.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools._pgtest import TEST_DATABASE_URL  # noqa: E402

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from tools import _pgtest as pgtest  # noqa: E402
from app import db  # noqa: E402


async def main() -> None:
    await pgtest.prepare()
    await db.init()
    all_ok = True

    def check(label: str, ok: bool) -> None:
        nonlocal all_ok
        print(f"  {'ok ' if ok else 'ОШИБКА'} {label}")
        all_ok = all_ok and ok

    # --- фикстура ---
    g = await db.upsert_group("Группа А", "2026-08-03", shift="morning")
    aya = await db.add_student(g, "Айя Ахметова", "9 класс", phone="+77011110001")
    bek = await db.add_student(g, "Бек Ким", "9 класс", phone="+77011110002")
    await db.link_student_tg(aya, 111)
    await db.link_student_tg(bek, 222)

    print("--- вход на платформу ---")
    token1, code1 = await db.issue_login_code("student", 111, student_id=aya)
    row = await db.q1("SELECT * FROM login_codes WHERE token_hash = ?",
                      hashlib.sha256(token1.encode()).hexdigest())
    check("строка найдена по sha256 ссылки", row is not None)
    check("сама ссылка в базе не хранится",
          not await db.q1("SELECT 1 FROM login_codes WHERE token_hash = ?", token1))
    check("код — шесть цифр", len(code1) == 6 and code1.isdigit() and row["code"] == code1)
    ttl = row["expires_at"] - row["created_at"]
    check(f"живёт {db.LOGIN_TTL_MINUTES} минут",
          abs(ttl - dt.timedelta(minutes=db.LOGIN_TTL_MINUTES)) < dt.timedelta(seconds=5))

    await db.issue_login_code("student", 222, student_id=bek)
    token2, _ = await db.issue_login_code("student", 111, student_id=aya)
    active = await db.q("SELECT tg_user_id FROM login_codes WHERE used_at IS NULL ORDER BY tg_user_id")
    check("повторный /login гасит прежний код того же человека",
          [r["tg_user_id"] for r in active] == [111, 222])
    check("и действует последний выданный",
          (await db.q1("SELECT used_at FROM login_codes WHERE token_hash = ?",
                       hashlib.sha256(token2.encode()).hexdigest()))["used_at"] is None)

    print("--- домашка ---")
    check("пока не сдал — homework_submitted ложь", not await db.homework_submitted(aya, 2))
    await db.run("INSERT INTO homework (student_id, day_index, text) VALUES (?, 2, 'mind map')", aya)
    check("сдал — homework_submitted истина", await db.homework_submitted(aya, 2))
    check("непроверенная сдача уведомлений не даёт", await db.homework_reviews_to_notify() == [])

    await db.run("UPDATE homework SET status = 'returned', mentor_comment = 'ещё ветки', "
                 "reviewed_at = now() WHERE student_id = ?", aya)
    due = await db.homework_reviews_to_notify()
    check("проверенная — к уведомлению, с tg ученика",
          len(due) == 1 and due[0]["tg_user_id"] == 111 and due[0]["status"] == "returned")

    first_review = due[0]["reviewed_at"]
    await db.run("UPDATE homework SET status = 'accepted', reviewed_at = now() + interval '1 second' "
                 "WHERE student_id = ?", aya)
    await db.mark_homework_notified(aya, 2, first_review)
    check("перепроверка во время отправки не теряется",
          len(await db.homework_reviews_to_notify()) == 1)

    latest = (await db.homework_reviews_to_notify())[0]["reviewed_at"]
    await db.mark_homework_notified(aya, 2, latest)
    check("после отметки уведомлять больше нечего", await db.homework_reviews_to_notify() == [])

    print("--- курс-директор ---")
    m = await db.grant_director("+77015550001", "Дина Директорова")
    check("до /start — None, запись в roster",
          m is None and (await db.roster_lookup("77015550001"))["is_director"])
    entry = await db.roster_lookup("77015550001")
    mid = await db.register_mentor(555, "77015550001", "Дина Директорова",
                                   is_admin=bool(entry["is_admin"]), is_mentor=bool(entry["is_mentor"]),
                                   is_director=bool(entry["is_director"]))
    row = await db.q1("SELECT * FROM mentors WHERE id = ?", mid)
    check("после /start — директор, но не админ и не ментор",
          row["is_director"] and not row["is_admin"] and not row["is_mentor"])
    await db.register_mentor(555, "77015550001", "Дина Директорова")
    check("повторная регистрация роль не снимает",
          (await db.mentor_by_tg(555))["is_director"])
    await db.add_to_roster("77015550001", "Дина Директорова", g)
    check("Excel-импорт (add_to_roster) роль в roster не снимает",
          (await db.roster_lookup("77015550001"))["is_director"])
    await db.register_mentor(666, "77015550002", "Марат Ментов")
    m = await db.grant_director("+77015550002", "Марат Ментов")
    check("уже в боте — роль сразу и ментор остаётся ментором",
          m is not None and (await db.mentor_by_tg(666))["is_director"]
          and (await db.mentor_by_tg(666))["is_mentor"])

    await db.close()
    print("\n" + ("ВСЁ ОК" if all_ok else "ЕСТЬ ОШИБКИ"))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
