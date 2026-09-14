"""Проверка JSON-импорта (новый контракт — сырая сетка от Google-таблицы,
см. integrations/sheets_sync.gs) без Telegram: python -m tools.test_json_import

Тот же сценарий, что в tools/test_excel.py (маркер «Настоящие группы
отсюда:», валидный блок + блок с кривой датой + ученик без имени + блок без
строки-заголовка группы), но переданный как {"rows": [[...], ...]} —
контракт, который реально шлёт integrations/sheets_sync.gs. Проверяет:

  1. валидный JSON импортируется, счётчики совпадают;
  2. source/spreadsheet/sheet/exported_at долетают до отчёта;
  3. повторный импорт того же JSON не плодит дублей (upsert-идемпотентность);
  4. импорт ТОЙ ЖЕ сетки через JSON и через эквивалентный .xlsx даёт
     одинаковый результат — доказательство, что оба формата реально идут
     через одно и то же ядро (app.roster_sheet.parse_grid + _import_core),
     а не продублированы;
  5. отсутствующий/битый ключ "rows" — понятная ошибка, а не падение.
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools._pgtest import TEST_DATABASE_URL  # noqa: E402

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import openpyxl  # noqa: E402

from tools import _pgtest as pgtest  # noqa: E402
from app import db  # noqa: E402
from app.handlers import admin  # noqa: E402

# --------------------------------------------------------------- та же сетка,
# что в tools/test_excel.py — см. там за комментарием к каждой строке.

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
    ["Группа А", "", "", "утро", "2026-08-03", ""],
    HEADER,
    ["Ментор Раз", "+77011112233", 1, "Ученик Один", "+77010000001", "9 класс", ""],
    [],
    ["Группа Б", "", "", "вечер", "не дата вообще", "оффлайн"],
    HEADER,
    ["Ментор Два", "+77012223344", 1, "Ученик Два", "", "9 класс", ""],
    ["", "", 2, "", "", "9 класс", ""],
    [],
    HEADER,
    ["Ментор Три", "+77013334455", 1, "Ученик Без Группы", "", "", ""],
]

EXPECTED = dict(
    groups_created=2, groups_updated=0,
    mentors_count=2, students_count=2,
    skipped_empty=0,
)


def build_json() -> dict:
    return {
        "source": "google-sheets",
        "spreadsheet": "Тестовая таблица PrimeTeens",
        "sheet": "Ростер",
        "exported_at": "2026-09-03T10:00:00Z",
        "rows": GRID,
    }


def build_equivalent_workbook():
    """Та же сетка, что build_json(), но в виде .xlsx-книги — для проверки,
    что оба формата идут через одно и то же ядро и дают одинаковый результат
    (см. check в main() ниже)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ростер"
    for row in GRID:
        ws.append(row)
    return wb


async def _snapshot() -> dict:
    """Срез состояния базы для сравнения JSON-импорта с xlsx-импортом: какие
    группы/менторы/ученики реально появились, без служебных id (они у разных
    прогонов будут разные)."""
    groups = {
        r["name"]: (r["start_date"], r["shift"], r["format"])
        for r in await db.q("SELECT name, start_date, shift, format FROM groups")
    }
    roster = {
        r["phone"]: (r["full_name"], r["is_admin"], r["is_mentor"],
                     (await db.q1("SELECT name FROM groups WHERE id = ?", r["group_id"]))["name"]
                     if r["group_id"] else None)
        for r in await db.q("SELECT phone, full_name, is_admin, is_mentor, group_id FROM roster")
    }
    students = {
        (r["full_name"], (await db.q1("SELECT name FROM groups WHERE id = ?", r["group_id"]))["name"],
         r["phone"])
        for r in await db.q("SELECT full_name, group_id, class_school, team, phone FROM students")
    }
    return {"groups": groups, "roster": roster, "students": students}


async def main() -> None:
    all_ok = True

    # ------------------------------------------------------------- JSON-импорт
    await pgtest.prepare()
    await db.init()
    print("--- первый JSON-импорт ---")
    data = build_json()
    report = await admin.import_json(data)

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

    joined = "".join(errors)
    checks = [
        ("кривая дата у «Группа Б» замечена", "не дата вообще" in joined),
        ("ученик без группы замечен", "Ученик Без Группы" in joined and "без группы" in joined),
        ("пропущенная строка учтена в сводке", "пропущено" in joined),
    ]
    for label, ok in checks:
        print(f"  {'ok ' if ok else 'ОШИБКА'} {label}")
        all_ok &= ok

    ok = (report.get("source") == "google-sheets"
          and report.get("spreadsheet") == "Тестовая таблица PrimeTeens"
          and report.get("sheet") == "Ростер"
          and report.get("exported_at") == "2026-09-03T10:00:00Z")
    print(f"\n  {'ok ' if ok else 'ОШИБКА'} source/spreadsheet/sheet/exported_at в отчёте: {ok}")
    all_ok &= ok

    formatted = "\n".join(admin._format_import_report(
        report, title="Синхронизация с Google-таблицей завершена."))
    ok = "google-sheets" in formatted and "Тестовая таблица PrimeTeens" in formatted \
        and "Ростер" in formatted
    print(f"  {'ok ' if ok else 'ОШИБКА'} метаданные попадают в текст отчёта: {ok}")
    all_ok &= ok

    snapshot_json = await _snapshot()

    # ------------------------------------------------------- повторный импорт
    print("\n--- повторный JSON-импорт того же набора (идемпотентность) ---")
    report2 = await admin.import_json(build_json())
    ok = report2["groups_created"] == 0 and report2["groups_updated"] == 2
    print(f"  {'ok ' if ok else 'ОШИБКА'} группы не создаются заново, а обновляются: "
          f"created={report2['groups_created']}, updated={report2['groups_updated']} (ждали 0/2)")
    all_ok &= ok

    students_total = (await db.q1(
        "SELECT COUNT(*) AS c FROM students WHERE full_name IN (?, ?)",
        "Ученик Один", "Ученик Два",
    ))["c"]
    ok = students_total == 2
    print(f"  {'ok ' if ok else 'ОШИБКА'} учеников по-прежнему 2, не 4 (upsert, не дубли): {ok}")
    all_ok &= ok

    # ------------------------------------------------------------- битые "rows"
    print("\n--- битый/отсутствующий ключ rows ---")
    bad_report = await admin.import_json({"source": "x"})
    ok = any("rows" in e for e in bad_report["errors"]) and bad_report["groups_created"] == 0
    print(f"  {'ok ' if ok else 'ОШИБКА'} отсутствие «rows» — понятная ошибка, не падение: {ok}")
    all_ok &= ok

    bad_report2 = await admin.import_json({"rows": "не список"})
    ok = any("rows" in e for e in bad_report2["errors"])
    print(f"  {'ok ' if ok else 'ОШИБКА'} «rows» не списком — тоже понятная ошибка: {ok}")
    all_ok &= ok

    await db.close()

    # -------------------------------------------------- эквивалентный .xlsx
    print("\n--- та же сетка через .xlsx (сверка общего ядра) ---")
    await pgtest.prepare()
    await db.init()
    wb = build_equivalent_workbook()
    report_xlsx = await admin.import_workbook(wb)

    for key in ("groups_created", "groups_updated", "mentors_count", "students_count",
                "skipped_empty"):
        got, want = report_xlsx[key], report[key]
        ok = got == want
        print(f"  {'ok ' if ok else 'ОШИБКА'} {key}: json={want}, xlsx={got}")
        all_ok &= ok

    snapshot_xlsx = await _snapshot()
    ok = snapshot_json == snapshot_xlsx
    print(f"  {'ok ' if ok else 'ОШИБКА'} итоговое состояние БД (группы/менторы/ученики) "
          f"совпадает у JSON- и xlsx-импорта: {ok}")
    if not ok:
        print(f"    json: {snapshot_json}")
        print(f"    xlsx: {snapshot_xlsx}")
    all_ok &= ok

    await db.close()
    print("\n" + ("ВСЁ ОК" if all_ok else "ЕСТЬ ОШИБКИ"))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
