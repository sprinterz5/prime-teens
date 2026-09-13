"""Проверка парсера реальной таблицы-ростера без Telegram и без Excel:
python -m tools.test_roster_sheet

Гоняет app.roster_sheet.parse_grid напрямую на сетках (списках списков) —
никакого openpyxl не открываем, это ниже уровнем, чем tools/test_excel.py.
Отдельно (в конце) собирает такую же сетку в реальный .xlsx через openpyxl
и through app.handlers.admin.import_workbook доходит до SQLite — доказывает,
что связка roster_sheet -> _import_core -> db реально работает end-to-end.

Кейсы:
  1. блоки «Шаблон» и «Пример» (выше маркера «Настоящие группы отсюда:»)
     не попадают в разбор вообще — только то, что ниже маркера;
  2. «Группа 1» существует и выше, и ниже маркера с РАЗНЫМИ датой/форматом —
     импортируется только та, что ниже (дата 21 сентября, формат online);
     это же доказывает, что дубли по имени между блоками не путаются;
  3. forward-fill ментора: все 7 учеников блока привязаны к одной группе,
     ментор в mentors ровно один (не по разу на строку);
  4. телефоны всех форматов из примера нормализуются одинаково;
  5. дата — приоритет у настоящего datetime/date-объекта (openpyxl), угадывание
     года по тексту «27 июля» — только запасной путь;
  6. таймзонная ловушка: ISO-строка с временем/UTC-хвостом не должна съезжать
     на день назад — берём только календарную дату из первых 10 символов;
  7. смена «Утренняя» -> morning, формат «Онлайн»/«Оффлайн» -> online/offline;
  8. «8» + «НИШ IB» -> class_school «8 класс, НИШ IB»;
  9. отсутствующий заголовок «Номер телефона» — телефон ментора берётся из
     колонки сразу справа от «Ментор»;
  10. строки без имени ученика — считаются, не считаются ошибкой;
  11. полный путь .xlsx -> import_workbook -> SQLite, включая повторный
      импорт той же сетки (идемпотентность, без дублей).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import os
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["DB_PATH"] = "data/test_roster_sheet.sqlite3"

from app import roster_sheet  # noqa: E402

ALL_OK = True


def check(label: str, ok: bool) -> None:
    global ALL_OK
    print(f"  {'ok ' if ok else 'ОШИБКА'} {label}")
    ALL_OK &= ok


# ------------------------------------------------------------------ фикстура
#
# Блок «Шаблон», блок «Пример» (Группа 1 / 27 июля (текст, без года) /
# Оффлайн), маркер, и настоящий блок «Группа 1» / 21 сентября 2026 (НАСТОЯЩИЙ
# date-объект, как отдаёт openpyxl) / Утренняя / Онлайн, с 7 учениками из
# присланного заказчиком скриншота. У РЕАЛЬНОГО блока заголовок «Номер
# телефона» пустой (данные лежат в колонке сразу за «Ментор») — так, как
# оказалось на самом деле у заказчика.

TEMPLATE_HEADER = ["Ментор", "Номер телефона", "#", "Ученик", "Контакты", "Школа", "Класс"]
REAL_HEADER = ["Ментор", "", "#", "Ученик", "Контакты", "Школа", "Класс"]

STUDENTS_RAW = [
    (1, "Тестов Арман Серикулы", "7 700 111 0070", "НИШ IB", 8),
    (2, "Примеров Амир", "7 700 111 7957", "РФМША", 7),
    (3, "Образцова Айлин Маратовна", "7 700 111 3033", "BINOM", 9),
    (4, "Демо Ерсұлтан Қанатұлы", "7 700 111 5177", "БИЛ", 9),
    (5, "Мадина", "77001113033", "БИЛ", 8),
    (6, "Нуржан", "87001110340", "БИЛ", 7),
    (7, "Султан", "87001117725", "БИЛ", 9),
]

EXPECTED_PHONES = {
    "Тестов Арман Серикулы": "77001110070",
    "Примеров Амир": "77001117957",
    "Образцова Айлин Маратовна": "77001113033",
    "Демо Ерсұлтан Қанатұлы": "77001115177",
    "Мадина": "77001113033",
    "Нуржан": "77001110340",
    "Султан": "77001117725",
}


def _real_block_rows(date_cell) -> list[list]:
    rows = [["Группа 1", "", "", "Утренняя", date_cell, "Онлайн"], REAL_HEADER]
    for i, (num, name, phone, school, klass) in enumerate(STUDENTS_RAW):
        if i == 0:
            rows.append(["Ерлан Тестов", "7 700 111 71 13", num, name, phone, school, klass])
        else:
            rows.append(["", "", num, name, phone, school, klass])
    return rows


def build_grid(date_cell=dt.date(2026, 9, 21)) -> list[list]:
    grid: list[list] = []
    grid.append(["ШАБЛОН — образец, не импортируется"])
    grid.append([])
    grid.append(["Группа А", "", "", "Утренняя", "27 июля", "Оффлайн"])
    grid.append(TEMPLATE_HEADER)
    grid.append(["Кто-то", "+7 700 000 00 00", 1, "Пример Ученик", "+7 700 000 00 01", "Школа", 9])
    grid.append([])
    grid.append(["ПРИМЕР — тоже не импортируется"])
    grid.append([])
    # «Группа 1» ВЫШЕ маркера — другая дата (текст без года) и другой формат.
    # Не должна попасть в импорт: ни как отдельная запись, ни подменить
    # собой настоящую «Группа 1» ниже маркера.
    grid.append(["Группа 1", "", "", "Утренняя", "27 июля", "Оффлайн"])
    grid.append(TEMPLATE_HEADER)
    grid.append(["Фейковый Ментор", "+7 700 000 00 02", 1, "Фейковый Ученик",
                 "+7 700 000 00 03", "Школа", 9])
    grid.append([])
    grid.append(["Настоящие группы отсюда:"])
    grid.append([])
    grid.extend(_real_block_rows(date_cell))
    grid.append([])  # пустая строка в конце блока, как на скриншоте — просто пропущена
    return grid


# ------------------------------------------------------------------- тесты

def test_basic() -> None:
    print("--- базовый разбор (дата — настоящий date-объект) ---")
    grid = build_grid()
    groups, mentors, students, problems = roster_sheet.parse_grid(grid)

    check("ровно одна группа «Группа 1» (не путает блок выше маркера)",
          len(groups) == 1 and groups[0]["name"] == "Группа 1")
    check("дата взята НИЖЕ маркера (2026-09-21), а не «27 июля» из блока выше",
          groups and groups[0]["start_date"] == "2026-09-21")
    check("смена «Утренняя» -> morning", groups and groups[0]["shift"] == "morning")
    check("формат «Онлайн» -> online (а не offline из блока выше маркера)",
          groups and groups[0]["format"] == "online")

    check("ровно один ментор (forward-fill, не по разу на ученика)", len(mentors) == 1)
    if mentors:
        m = mentors[0]
        check("ментор — Ерлан Тестов", m["full_name"] == "Ерлан Тестов")
        check("группа ментора — «Группа 1»", m["group"] == "Группа 1")
        check("телефон ментора взят из колонки сразу за «Ментор» "
              "(заголовок «Номер телефона» пустой)", m["phone"] == "7 700 111 71 13")

    check("ровно 7 учеников (шаблон/пример не примешались)", len(students) == 7)
    names = {s["full_name"] for s in students}
    check("все 7 настоящих учеников на месте",
          names == set(EXPECTED_PHONES) and "Пример Ученик" not in names
          and "Фейковый Ученик" not in names)
    for s in students:
        check(f"группа ученика «{s['full_name']}» — «Группа 1»", s["group"] == "Группа 1")

    check("«8» + «НИШ IB» -> class_school «8 класс, НИШ IB»",
          any(s["full_name"] == "Тестов Арман Серикулы"
              and s["class_school"] == "8 класс, НИШ IB" for s in students))

    print("\n  телефоны учеников:")
    for s in students:
        got = None
        try:
            from app import db
            got = db.norm_phone(s["phone"])
        except Exception:
            pass
        want = EXPECTED_PHONES[s["full_name"]]
        ok = got == want
        print(f"    {'ok ' if ok else 'ОШИБКА'} {s['full_name']}: «{s['phone']}» -> {got} (ждали {want})")
        global ALL_OK
        ALL_OK &= ok

    check("отчёт содержит полную распознанную дату группы (21.09.2026)",
          any("21.09.2026" in p for p in problems))
    check("шаблон/пример НЕ упомянуты как импортированные проблемы про их учеников",
          not any("Пример Ученик" in p or "Фейковый Ученик" in p for p in problems))


def test_guessed_year_from_text() -> None:
    print("\n--- дата без года текстом (запасной путь, эвристика 120 дней) ---")
    grid = build_grid(date_cell="21 сентября")
    groups, _, _, problems = roster_sheet.parse_grid(grid)
    check("группа нашлась", len(groups) == 1)
    if not groups:
        return
    iso = groups[0]["start_date"]
    ok = iso is not None
    check("дата распознана из текста без года", ok)
    if ok:
        d = dt.date.fromisoformat(iso)
        check("день/месяц совпадают с «21 сентября»", (d.month, d.day) == (9, 21))
        today = dt.date.today()
        ok_year = (today - d).days <= 120 or d.year == today.year + 1
        check("год выбран по правилу 120 дней", ok_year)
    check("в отчёте есть пометка «год угадан» — админ должен проверить",
          any("год угадан" in p for p in problems))


def test_real_date_object_wins_over_guessing() -> None:
    print("\n--- приоритет настоящего date-объекта над угадыванием года ---")
    # Настоящая дата — 27.07.2026 (>120 дней в прошлом от текущей даты во
    # многих сценариях), но раз это НАСТОЯЩИЙ date-объект — эвристика вообще
    # не должна включаться, дата берётся как есть, без "переноса на год вперёд".
    grid = build_grid(date_cell=dt.date(2026, 7, 27))
    groups, _, _, problems = roster_sheet.parse_grid(grid)
    check("группа нашлась", len(groups) == 1)
    if groups:
        check("дата — ровно 2026-07-27, без сдвига года", groups[0]["start_date"] == "2026-07-27")
    check("настоящая дата не помечена как «угадана» (эвристика не применялась)",
          not any("год угадан" in p and "27.07.2026" in p for p in problems))


def test_timezone_trap() -> None:
    """Ловушка часовых поясов: если дата всё же доехала в виде ISO-строки С
    ВРЕМЕНЕМ (например, «сырой» Date без форматирования на стороне Apps
    Script — JSON.stringify отдаёт UTC), 27.07.2026 00:00 в Алматы (+5) — это
    "2026-07-26T19:00:00.000Z". Разбор должен брать календарную дату из
    первых 10 символов, НЕ пересчитывая по часовому поясу — иначе дата
    молча съедет на день назад."""
    print("\n--- таймзонная ловушка (ISO-строка с UTC-хвостом) ---")
    grid = build_grid(date_cell="2026-07-26T19:00:00.000Z")
    groups, _, _, _ = roster_sheet.parse_grid(grid)
    check("группа нашлась", len(groups) == 1)
    if groups:
        # Календарная дата в самой строке — 26 июля (это и есть "сырой" факт
        # строки), а не 27-е: тест доказывает, что мы её НЕ ДОГАДЫВАЕМ и не
        # сдвигаем по TZ, а берём буквально то, что в первых 10 символах.
        check("взята календарная дата из строки как есть, без сдвига по TZ",
              groups[0]["start_date"] == "2026-07-26")

    print("  (эта же строка, но как её реально отдаёт формула Utilities.formatDate "
        "из integrations/sheets_sync.gs — просто 'yyyy-MM-dd', без времени/зоны)")
    grid2 = build_grid(date_cell="2026-07-27")
    groups2, _, _, _ = roster_sheet.parse_grid(grid2)
    check("после исправления в .gs (дата форматируется в скрипте) дата верна: 2026-07-27",
          groups2 and groups2[0]["start_date"] == "2026-07-27")


def test_no_marker_warns() -> None:
    print("\n--- нет строки-маркера ---")
    grid = build_grid()
    grid_no_marker = [r for r in grid if r != ["Настоящие группы отсюда:"]]
    groups, _, _, problems = roster_sheet.parse_grid(grid_no_marker)
    check("без маркера разбирает всё (шаблон+пример тоже попадают в groups)",
          len(groups) >= 2)
    check("есть предупреждение про отсутствие маркера",
          any("маркер" in p.lower() for p in problems))


def test_blank_rows_counted_not_errors() -> None:
    print("\n--- пустые строки / строки без имени ученика ---")
    grid = build_grid()
    # добавим внутрь настоящего блока пустую строку-разрыв внутри
    # student-диапазона -> она обрывает блок (как и настоящий пробел между
    # группами), это ожидаемо. Отдельно проверим строку "без имени, но с
    # телефоном" -> считается, не ошибка.
    # строка с "#"=8 но без имени ученика (пустая ячейка «Ученик»)
    insert_at = len(grid) - 1  # перед завершающей пустой строкой
    grid.insert(insert_at, ["", "", 8, "", "", "", ""])
    groups, mentors, students, problems = roster_sheet.parse_grid(grid)
    check("строка без имени ученика не попала в students", len(students) == 7)
    check("она посчитана в отчёте как пропущенная, а не как ошибка",
          any("пропущено" in p for p in problems)
          and not any("строка вне блока" in p for p in problems))


def test_orphan_student_no_group() -> None:
    print("\n--- ученик есть, а строки-заголовка группы перед шапкой колонок нет ---")
    grid = [
        ["Настоящие группы отсюда:"],
        TEMPLATE_HEADER,  # шапка колонок сразу, без строки-заголовка группы перед ней
        ["Ментор Одинокий", "+7 700 000 00 05", 1, "Ученик Без Группы",
         "+7 700 000 00 06", "Школа", 9],
    ]
    groups, mentors, students, problems = roster_sheet.parse_grid(grid)
    check("группа не создана", len(groups) == 0)
    check("ученик не добавлен", len(students) == 0)
    check("проблема с номером строки про ученика без группы есть",
          any("Ученик Без Группы" in p and "без группы" in p for p in problems))


async def test_end_to_end_xlsx() -> None:
    print("\n--- полный путь: .xlsx -> import_workbook -> SQLite ---")
    import openpyxl
    from app import db
    from app.config import settings
    from app.handlers import admin

    settings.db_path.unlink(missing_ok=True)
    await db.init()

    grid = build_grid()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "roster.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        for row in grid:
            ws.append(row)
        wb.save(path)

        wb2 = openpyxl.load_workbook(path, data_only=True)
        report = await admin.import_workbook(wb2)
        check("группа создана 1 раз", report["groups_created"] == 1)
        check("менторов в ростере: 1", report["mentors_count"] == 1)
        check("учеников: 7", report["students_count"] == 7)

        g = await db.q1("SELECT * FROM groups WHERE name = ?", "Группа 1")
        check("группа в БД со стартом 2026-09-21", g and g["start_date"] == "2026-09-21")
        check("группа в БД с форматом online", g and g["format"] == "online")
        check("группа в БД со сменой morning", g and g["shift"] == "morning")

        st = await db.q1("SELECT * FROM students WHERE full_name = ?", "Тестов Арман Серикулы")
        check("телефон ученика в БД нормализован", st and st["phone"] == "77001110070")
        check("класс/школа ученика в БД собраны вместе",
              st and st["class_school"] == "8 класс, НИШ IB")

        roster_row = await db.q1("SELECT * FROM roster WHERE phone = ?", "77001117113")
        check("ментор в roster с правильным именем",
              roster_row and roster_row["full_name"] == "Ерлан Тестов")

        print("\n--- повторный импорт того же файла (идемпотентность) ---")
        wb3 = openpyxl.load_workbook(path, data_only=True)
        report2 = await admin.import_workbook(wb3)
        check("группа не создаётся заново, а обновляется",
              report2["groups_created"] == 0 and report2["groups_updated"] == 1)
        students_total = (await db.q1(
            "SELECT COUNT(*) AS c FROM students WHERE group_id = ?", g["id"]))["c"]
        check("учеников по-прежнему 7, не 14 (не дублируются)", students_total == 7)
        mentors_total = (await db.q1(
            "SELECT COUNT(*) AS c FROM roster WHERE phone = ?", "77001117113"))["c"]
        check("ментор в roster по-прежнему один", mentors_total == 1)

    await db.close()
    settings.db_path.unlink(missing_ok=True)


async def main() -> None:
    test_basic()
    test_guessed_year_from_text()
    test_real_date_object_wins_over_guessing()
    test_timezone_trap()
    test_no_marker_warns()
    test_blank_rows_counted_not_errors()
    test_orphan_student_no_group()
    await test_end_to_end_xlsx()

    print("\n" + ("ВСЁ ОК" if ALL_OK else "ЕСТЬ ОШИБКИ"))
    sys.exit(0 if ALL_OK else 1)


if __name__ == "__main__":
    asyncio.run(main())
