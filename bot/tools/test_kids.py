"""Проверка детского бота без Telegram: python -m tools.test_kids

Что проверяем:
  1. Привязка Telegram-аккаунта к ученику — по персональной ссылке и по
     телефону (в т.ч. семейный номер на двоих детей).
  2. Отзыв об уроке анонимен ПО СТРУКТУРЕ ЗАПРОСА: group_kid_feedback()
     физически не может вернуть имя ученика, потому что не выбирает его —
     это регрессионный тест на будущее, если кто-то потом "улучшит" запрос.
  3. Повторный отзыв за тот же день заменяет прежний, а не плодит дубли.
  4. Команда на хакатон: создание капитаном синхронизирует students.team в
     менторской базе, вступление по коду работает кросс-группово (сейчас
     разрешено намеренно), выход из команды снова обнуляет team.
  5. Персональная ссылка ученика (role='student') — одноразовая, с теми же
     статусами, что и у ментора/админа (общий код в db.py).
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["DB_PATH"] = "data/test_kids.sqlite3"

from app import db  # noqa: E402
from app.config import settings  # noqa: E402


async def main() -> None:
    settings.db_path.unlink(missing_ok=True)
    await db.init()
    all_ok = True

    def check(label: str, ok: bool) -> None:
        nonlocal all_ok
        print(f"  {'ok ' if ok else 'ОШИБКА'} {label}")
        all_ok = all_ok and ok

    # --- фикстура ---
    ga = await db.upsert_group("Группа А", "2026-08-03", shift="morning")
    gb = await db.upsert_group("Группа Б", "2026-08-03", shift="evening")
    airi = await db.add_student(ga, "Айя Ахметова", "9 класс", phone="+77011110001")
    bogdan = await db.add_student(ga, "Богдан Ким", "9 класс", phone="+77011110002")
    sib1 = await db.add_student(ga, "Сестра Одна", "8 класс", phone="+77011110099")
    sib2 = await db.add_student(gb, "Брат Два", "7 класс", phone="+77011110099")  # тот же номер
    victoria = await db.add_student(gb, "Виктория Ли", "8 класс", phone="+77011110003")

    print("--- привязка аккаунта ---")
    matches = await db.students_by_phone("77011110099")
    check("семейный номер даёт двух кандидатов", len(matches) == 2)

    matches1 = await db.students_by_phone("+7 701 111 00 01")
    check("обычный номер даёт ровно одного", len(matches1) == 1 and matches1[0]["id"] == airi)

    await db.link_student_tg(airi, 111222333)
    linked = await db.student_by_tg(111222333)
    check("student_by_tg находит привязанного", linked is not None and linked["id"] == airi)
    check("student_by_tg не находит непривязанного", (await db.student_by_tg(999999)) is None)

    # --- персональная ссылка ---
    print("\n--- персональная ссылка ученика (одноразовая) ---")
    token = "kidtok123"
    await db.create_invite(token, ga, created_by=1, role="student", student_id=bogdan)
    check("статус свежей ссылки — ok", await db.invite_status(token, 555) == "ok")
    claimed = await db.claim_invite(token, 555)
    check("claim первым — ok", claimed == "ok")
    check("тот же tg — used_by_self", await db.invite_status(token, 555) == "used_by_self")
    check("другой tg — used_by_other", await db.invite_status(token, 777) == "used_by_other")
    await db.link_student_tg(bogdan, 555, phone="+77011110002")
    check("телефон не потерялся после привязки",
         (await db.student(bogdan))["phone"] == "77011110002")

    # --- отзыв: анонимность по структуре запроса ---
    print("\n--- отзыв об уроке ---")
    await db.save_kid_feedback(airi, ga, 1, 5, "Было интересно, особенно дебаты", "voice")
    check("kid_feedback_done — True сразу после отправки",
         await db.kid_feedback_done(airi, 1))
    check("kid_feedback_done — False для другого дня",
         not await db.kid_feedback_done(airi, 2))

    rows = await db.group_kid_feedback(ga, 1)
    check("отзыв нашёлся в выборке по группе/дню", len(rows) == 1)
    row_keys = set(rows[0].keys())
    check("в выборке НЕТ full_name (структурная анонимность)",
         "full_name" not in row_keys and "student_id" not in row_keys)
    check("текст отзыва дошёл как есть", rows[0]["text"] == "Было интересно, особенно дебаты")

    await db.save_kid_feedback(airi, ga, 1, 2, "Передумала, было скучно", "text")
    rows2 = await db.group_kid_feedback(ga, 1)
    check("повторный отзыв за тот же день заменил прежний, не добавил новый",
         len(rows2) == 1 and rows2[0]["rating"] == 2)

    await db.save_kid_feedback(bogdan, ga, 1, 4, None, "text")
    stats = await db.kid_feedback_stats(ga)
    check("статистика по дню: 2 отзыва, среднее 3.0",
         stats.get(1, {}).get("count") == 2 and abs(stats[1]["avg"] - 3.0) < 1e-6)

    # --- хакатон: команды ---
    print("\n--- команды на хакатон ---")
    team_id = await db.create_hack_team("Nova", "Кейс про экономику", airi, "code123")
    leader_team = await db.hack_team_of_student(airi)
    check("капитан состоит в своей команде", leader_team is not None and leader_team["id"] == team_id)
    check("students.team синхронизирован для капитана",
         (await db.student(airi))["team"] == "Nova")

    by_code = await db.hack_team_by_code("code123")
    check("команда находится по коду", by_code is not None and by_code["id"] == team_id)

    # вступает ученик из ДРУГОЙ группы — кросс-групповые команды разрешены сейчас
    await db.join_hack_team(team_id, victoria)
    check("students.team синхронизирован для вступившего из другой группы",
         (await db.student(victoria))["team"] == "Nova")
    members = await db.hack_team_members(team_id)
    check("в команде двое, из разных групп",
         len(members) == 2 and {m["group_id"] for m in members} == {ga, gb})

    await db.leave_hack_team(victoria)
    check("вышедший больше не числится в команде",
         (await db.hack_team_of_student(victoria)) is None)
    check("students.team обнулился после выхода",
         (await db.student(victoria))["team"] is None)
    members_after = await db.hack_team_members(team_id)
    check("капитан остался в команде один", len(members_after) == 1)

    await db.close()
    settings.db_path.unlink(missing_ok=True)
    print("\n" + ("ВСЁ ОК" if all_ok else "ЕСТЬ ОШИБКИ"))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
