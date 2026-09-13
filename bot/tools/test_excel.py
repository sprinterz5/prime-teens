"""Проверка Excel-импорта (новый формат — один лист, блоки групп) без
Telegram: python -m tools.test_excel

Собирает временный .xlsx с сеткой (маркер «Настоящие группы отсюда:» + два
блока групп: валидный и с проблемами — кривая дата в заголовке, ученик без
имени, блок без строки-заголовка группы) и прогоняет через
app.handlers.admin.import_workbook (та же функция, что дёргает бот при
получении .xlsx). Более детальный разбор самого формата (forward-fill,
телефоны, даты, маркер) — в tools/test_roster_sheet.py; здесь фокус на том,
что .xlsx корректно долетает до этого разбора и до БД. Проверяет:

  1. правильные числа созданного/обновлённого;
  2. проблемные места собраны с номером строки;
  3. повторный импорт того же файла не плодит дублей (upsert-идемпотентность).
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["DB_PATH"] = "data/test_excel.sqlite3"

import openpyxl  # noqa: E402

from app import db, roster_sheet  # noqa: E402
from app.config import settings  # noqa: E402
from app.handlers import admin  # noqa: E402

# --------------------------------------------------------------- сетка файла

HEADER = ["Ментор", "Номер телефона", "#", "Ученик", "Контакты", "Школа", "Класс"]

GRID = [
    ["Шаблон — не импортируется"],
    [],
    ["Группа-шаблон", "", "", "утро", "27 июля", "оффлайн"],
    HEADER,
    ["Никто", "+70000000000", 1, "Никто Не Импортируется", "", "", ""],
    [],
    ["Настоящие группы отсюда:"],
    [],
    # ---- Группа А: валидный блок --------------------------------------
    ["Группа А", "", "", "утро", "2026-08-03", ""],
    HEADER,
    ["Ментор Раз", "+77011112233", 1, "Ученик Один", "+77010000001", "9 класс", ""],
    [],
    # ---- Группа Б: кривая дата в заголовке, ученик без имени -----------
    ["Группа Б", "", "", "вечер", "не дата вообще", "оффлайн"],
    HEADER,
    ["Ментор Два", "+77012223344", 1, "Ученик Два", "", "9 класс", ""],
    ["", "", 2, "", "", "9 класс", ""],   # без имени -> пропущена молча (считается)
    [],
    # ---- блок без строки-заголовка группы (шапка сразу после пустой) ---
    HEADER,
    ["Ментор Три", "+77013334455", 1, "Ученик Без Группы", "", "", ""],
]

EXPECTED = dict(
    groups_created=2, groups_updated=0,
    mentors_count=2, students_count=2,
    skipped_empty=0,
)


def build_workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ростер"
    for row in GRID:
        ws.append(row)
    wb.save(path)


async def main() -> None:
    settings.db_path.unlink(missing_ok=True)
    await db.init()
    all_ok = True

    with tempfile.TemporaryDirectory() as tmp:
        xlsx_path = Path(tmp) / "test_import.xlsx"
        build_workbook(xlsx_path)
        print(f"--- собран временный файл: {xlsx_path} ---\n")

        print("--- первый импорт ---")
        wb = openpyxl.load_workbook(xlsx_path, data_only=True)
        report = await admin.import_workbook(wb)

        for key in ("groups_created", "groups_updated", "mentors_count", "students_count",
                    "skipped_empty"):
            got = report[key]
            want = EXPECTED[key]
            ok = got == want
            print(f"  {'ok ' if ok else 'ОШИБКА'} {key}: {got} (ждали {want})")
            all_ok &= ok

        errors = report["errors"]
        print(f"\n  проблемные места ({len(errors)}):")
        for e in errors:
            print(f"    {e}")

        # Каждая НАСТОЯЩАЯ проблема называет номер строки — иначе админ не
        # найдёт, что чинить в файле. Справочные пометки (INFO_PREFIX:
        # разрешённая дата старта, сводка по пропущенным пустым строкам)
        # от этого требования освобождены — они не про «пойди и почини».
        row_tagged = [e for e in errors if not str(e).startswith(roster_sheet.INFO_PREFIX)]
        bad_format = [e for e in row_tagged if not re.search(r"строка \d+", e)]
        ok = not bad_format
        print(f"\n  {'ok ' if ok else 'ОШИБКА'} у каждой непустой проблемы указан номер строки: {ok}")
        all_ok &= ok

        joined = "".join(errors)
        checks = [
            ("кривая дата у «Группа Б» замечена", "не дата вообще" in joined),
            ("ученик без группы (блок без заголовка) замечен",
             "Ученик Без Группы" in joined and "без группы" in joined),
            ("пропущенная (без имени) строка учтена в сводке", "пропущено" in joined),
            ("шаблон не упомянут ни в одной проблеме", "Никто Не Импортируется" not in joined),
        ]
        for label, ok in checks:
            print(f"  {'ok ' if ok else 'ОШИБКА'} {label}")
            all_ok &= ok

        # --------------------------------------------------------- DB-факты
        groups_in_db = {r["name"]: r["id"] for r in await db.q(
            "SELECT id, name FROM groups WHERE name IN (?, ?)", "Группа А", "Группа Б",
        )}
        ok = set(groups_in_db) == {"Группа А", "Группа Б"}
        print(f"\n  {'ok ' if ok else 'ОШИБКА'} обе валидные группы реально в БД: {ok}")
        all_ok &= ok

        a_row = await db.q1("SELECT start_date, shift FROM groups WHERE name = ?", "Группа А")
        ok = a_row is not None and a_row["start_date"] == "2026-08-03" and a_row["shift"] == "morning"
        print(f"  {'ok ' if ok else 'ОШИБКА'} «Группа А»: дата 2026-08-03, смена morning: {ok}")
        all_ok &= ok

        b_row = await db.q1("SELECT start_date, format FROM groups WHERE name = ?", "Группа Б")
        ok = b_row is not None and b_row["start_date"] is None and b_row["format"] == "offline"
        print(f"  {'ok ' if ok else 'ОШИБКА'} «Группа Б» без даты (кривая), но формат offline распознан: {ok}")
        all_ok &= ok

        roster_count = (await db.q1(
            "SELECT COUNT(*) AS c FROM roster WHERE phone IN (?, ?)",
            "77011112233", "77012223344",
        ))["c"]
        ok = roster_count == 2
        print(f"  {'ok ' if ok else 'ОШИБКА'} в roster ровно 2 валидных ментора: {ok}")
        all_ok &= ok

        students_count_db = (await db.q1(
            "SELECT COUNT(*) AS c FROM students WHERE full_name IN (?, ?)",
            "Ученик Один", "Ученик Два",
        ))["c"]
        ok = students_count_db == 2
        print(f"  {'ok ' if ok else 'ОШИБКА'} в students ровно 2 валидных ученика: {ok}")
        all_ok &= ok

        no_such = await db.q1("SELECT 1 FROM students WHERE full_name = ?", "Ученик Без Группы")
        ok = no_such is None
        print(f"  {'ok ' if ok else 'ОШИБКА'} «Ученик Без Группы» в БД не попал: {ok}")
        all_ok &= ok

        # ------------------------------------------------------- повторный импорт
        print("\n--- повторный импорт того же файла (идемпотентность) ---")
        wb2 = openpyxl.load_workbook(xlsx_path, data_only=True)
        report2 = await admin.import_workbook(wb2)

        ok = report2["groups_created"] == 0 and report2["groups_updated"] == 2
        print(f"  {'ok ' if ok else 'ОШИБКА'} второй раз группы не создаются заново, "
              f"а обновляются: created={report2['groups_created']}, "
              f"updated={report2['groups_updated']} (ждали 0/2)")
        all_ok &= ok

        groups_total = (await db.q1(
            "SELECT COUNT(*) AS c FROM groups WHERE name IN (?, ?)", "Группа А", "Группа Б",
        ))["c"]
        ok = groups_total == 2
        print(f"  {'ok ' if ok else 'ОШИБКА'} групп в БД по-прежнему 2, не 4: {ok}")
        all_ok &= ok

        roster_total = (await db.q1(
            "SELECT COUNT(*) AS c FROM roster WHERE phone IN (?, ?)",
            "77011112233", "77012223344",
        ))["c"]
        ok = roster_total == 2
        print(f"  {'ok ' if ok else 'ОШИБКА'} менторов в roster по-прежнему 2, не 4: {ok}")
        all_ok &= ok

        students_total = (await db.q1(
            "SELECT COUNT(*) AS c FROM students WHERE full_name IN (?, ?)",
            "Ученик Один", "Ученик Два",
        ))["c"]
        ok = students_total == 2
        print(f"  {'ok ' if ok else 'ОШИБКА'} учеников по-прежнему 2, не 4 (upsert, не дубли): {ok}")
        all_ok &= ok

    await db.close()
    settings.db_path.unlink(missing_ok=True)
    print("\n" + ("ВСЁ ОК" if all_ok else "ЕСТЬ ОШИБКИ"))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
