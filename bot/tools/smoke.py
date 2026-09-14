"""Прогон всей логики без Telegram: python -m tools.smoke

Симулирует курс на 8 учениках: стартовый замер, шесть уроков с исключениями,
хакатон, финальный замер. Главная проверка — сколько шагов реально проходит
ментор после урока (ТЗ целится в 3–4 минуты на 8 человек).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import os
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["LLM_PROVIDER"] = "off"

from tools._pgtest import TEST_DATABASE_URL  # noqa: E402

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from tools import _pgtest as pgtest  # noqa: E402
from app import db, dossier, flow  # noqa: E402
from app.config import COURSE  # noqa: E402

STUDENTS = [
    ("Ахметова Айя", "9 класс, НИШ", "Nova"),
    ("Ким Богдан", "9 класс, НИШ", "Nova"),
    ("Ли Виктория", "8 класс, Гимназия 5", "Nova"),
    ("Оспанов Нариман", "9 класс, Лицей 66", "Nova"),
    ("Сейткали Алия", "10 класс, НИШ", "Nomad"),
    ("Сериков Акпай", "8 класс, НИШ", "Nomad"),
    ("Жумабек Абзалхан", "9 класс, Гимназия 5", "Nomad"),
    ("Турсын Алан", "8 класс, Лицей 66", "Nomad"),
]


async def fill(session_id, gid, day, steps, answers_map, students):
    """Проходит шаги, подставляя ответы. Возвращает, сколько шагов реально задано."""
    asked = 0
    given = {}
    i = 0
    while i < len(steps):
        s = steps[i]
        if not flow.should_ask(s, given):
            i += 1
            continue
        asked += 1
        val, txt = answers_map(s, students)
        given[s["key"]] = val if not isinstance(val, list) else val
        if s["type"] == "students_multi":
            chosen = [st for st in students if st["id"] in (val or [])]
            await db.save_answer(session_id, gid, day, s["key"], s["text"], s["maps_to"],
                                 None, ",".join(map(str, val or [])),
                                 ", ".join(x["short_name"] for x in chosen) or "никто",
                                 "button")
            for c in chosen:
                await db.save_answer(session_id, gid, day, s["key"] + "_mark", s["text"],
                                     s["maps_to"], c["id"], "1", "да", "button")
            extra = flow.expand_for(s, chosen)
            steps = steps[:i + 1] + extra + steps[i + 1:]
        else:
            await db.save_answer(session_id, gid, day, s["key"], s["text"], s["maps_to"],
                                 s["student_id"], str(val) if val is not None else None,
                                 txt, "voice" if s["voice"] else "button")
        i += 1
    return asked, steps


def lesson_answers(day):
    def inner(s, students):
        k = s["key"]
        if k == "pulse":
            return ("hard" if day == 3 else "ok"), "Ровно"
        if k == "pulse_why":
            return None, "Проектор не работал, потеряли двадцать минут."
        if k == "absent":
            return ([students[7]["id"]] if day in (2, 5) else []), None
        if k == "standout":
            return ([students[0]["id"]] if day % 2 else [students[1]["id"]]), None
        if k == "standout_tags":
            return "idea", "💡 Своя идея"
        if k == "episode":
            return None, "Переспорил команду и отстоял свой вариант интерфейса."
        if k == "struggled":
            return ([students[5]["id"]] if day == 3 else []), None
        if k == "struggled_tags":
            return "silent", "😶 Молчал весь урок"
        if k == "spotlight_mode":
            return "proposed", "Сам предлагал"
        if k == "spotlight_episode":
            return None, "Разобрал чужой постер и предложил переписать вывод."
        if k == "homework":
            return ([students[6]["id"]] if day == 5 else []), None
        return None, "ответ"
    return inner


async def main() -> None:
    await pgtest.prepare()
    await db.init()
    start = (dt.date.today() - dt.timedelta(days=13)).isoformat()
    # Две смены — один и тот же старт и офсеты, разное время занятий.
    gid = await db.upsert_group("Группа Айдара · утро", start, shift="morning")
    gid_evening = await db.upsert_group("Группа Айдара · вечер", start, shift="evening")
    mid = await db.register_mentor(111, "+77011112233", "Айдар", True)
    await db.link_mentor_group(mid, gid)
    for name, cls, team in STUDENTS:
        await db.add_student(gid, name, cls, team)
    students = await db.students(gid)
    print(f"группа: {len(students)} учеников, старт {start}\n")

    print("расписание смен (дни одинаковые, время — нет):")
    for d in COURSE["days"]:
        wm = await db.group_lesson_window(gid, d["index"])
        we = await db.group_lesson_window(gid_evening, d["index"])
        if wm is None or we is None:
            continue
        sm, em = wm
        se, ee = we
        print(f"  день {d['index']} · {d['weekday']:<11} "
              f"утро {sm.strftime('%H:%M')}–{em.strftime('%H:%M')}   "
              f"вечер {se.strftime('%H:%M')}–{ee.strftime('%H:%M')}")
    print()

    # --- стартовый замер ---
    steps = flow.build_steps("baseline", students)
    ses = await db.open_session(mid, gid, 1, "baseline")
    n = 0
    for i, s in enumerate(steps):
        v = str(3 + (i % 4)) if s["type"] == "scale10" else None
        await db.save_answer(ses, gid, 1, s["key"], s["text"], s["maps_to"],
                             s["student_id"], v,
                             v or "Игры, дизайн, немного биологии.", "voice")
        n += 1
    await db.finish_session(ses)
    print(f"стартовый замер: {n} шагов на {len(students)} учеников "
          f"({n // len(students)} на каждого)")

    # --- уроки ---
    print("\nопрос после урока (главная метрика ТЗ):")
    for day in (2, 3, 4, 5, 6, 7):
        eps = await db.episode_counts(gid)
        spot = flow.pick_spotlight(students, eps, await db.spotlight_counts(gid))
        steps = flow.build_steps("lesson", students, spotlight=spot)
        ses = await db.open_session(mid, gid, day, "lesson")
        asked, _ = await fill(ses, gid, day, steps, lesson_answers(day), students)
        await db.finish_session(ses)
        print(f"  день {day}: {asked} шагов · прожектор — "
              f"{', '.join(s['short_name'] for s in spot)}")

    # --- хакатон ---
    teams = sorted({s["team"] for s in students if s["team"]})
    steps = flow.build_steps("hackathon", students, teams=teams)
    ses = await db.open_session(mid, gid, 9, "hackathon")
    for s in steps:
        await db.save_answer(ses, gid, 9, s["key"], s["text"], s["maps_to"],
                             s["student_id"], "2" if s["key"] == "team_place" else "main",
                             "2 место" if s["key"] == "team_place"
                             else "Собрала экономику решения и защитила цифры.", "voice")
    await db.finish_session(ses)
    print(f"\nхакатон: {len(steps)} шагов на {len(teams)} команды и {len(students)} учеников")

    # --- финальный замер ---
    eps = await db.episode_counts(gid)
    steps = flow.build_steps("final", students, episode_counts=eps)
    ses = await db.open_session(mid, gid, 0, "final")
    for i, s in enumerate(steps):
        v = str(5 + (i % 5)) if s["type"] == "scale10" else None
        await db.save_answer(ses, gid, 0, s["key"], s["text"], s["maps_to"],
                             s["student_id"], v, v or "Запомнился спор на защите.", "voice")
    await db.finish_session(ses)
    print(f"финальный замер: {len(steps)} шагов "
          f"(добор эпизодов только тем, у кого их меньше двух)")

    # --- покрытие ---
    print("\nэпизодов на ученика (цель ТЗ — минимум 2, ноль недопустим):")
    eps = await db.episode_counts(gid)
    zero = []
    for s in students:
        c = eps.get(s["id"], 0)
        flag = "🔴" if c == 0 else ("🟡" if c == 1 else "🟢")
        if c == 0:
            zero.append(s["short_name"])
        print(f"  {flag} {s['short_name']:12} {c}")
    print(f"  без единого эпизода: {zero or 'нет — цель достигнута'}")

    # --- выгрузка ---
    zip_path, html_path, stats = await dossier.export_group(gid)
    print(f"\nвыгрузка: {stats}")
    with zipfile.ZipFile(zip_path) as z:
        print("  " + " · ".join(n.split("/")[-1] for n in z.namelist()))
    print(f"  HTML: {html_path.name} ({html_path.stat().st_size} байт)")

    await db.close()
    print("\nOK")


if __name__ == "__main__":
    asyncio.run(main())
