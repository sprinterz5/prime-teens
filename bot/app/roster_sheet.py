"""Парсер реальной таблицы-ростера: один лист, сверху вниз блоки групп.

Формат листа (см. integrations/README.md за картинкой и integrations/sheets_sync.gs
за тем, как сетка попадает сюда из Google-таблицы):

  Группа 1 | | | Утренняя | 27 июля | Онлайн        <- строка-заголовок блока
  Ментор | Номер телефона | # | Ученик | Контакты | Школа | Класс   <- заголовки колонок
  Ерлан Тестов | 7 700 111 71 13 | 1 | Тестов Арман | 7 700 111 0070 | НИШ IB | 8
                                       | 2 | Примеров Амир | ...

Название/смена/дата/формат в строке-заголовке блока могут стоять в любых
колонках — ищем по смыслу значения, а не по индексу. Ментор и его телефон
заполнены только в первой строке блока (дальше визуально "объединены" —
на деле просто пусто) — протягиваем вниз, пока не начнётся новый блок.

Перед реальными данными в таблице лежат демонстрационные блоки «Шаблон» и
«Пример», которые импортировать нельзя — их отсекает строка-маркер
«Настоящие группы отсюда:» (регистр и пробелы/двоеточие не важны, достаточно
вхождения «настоящие группы»): всё, что выше и включая эту строку, в разбор
не идёт. Нет маркера — разбираем всё, но с предупреждением в problems.

Публичная функция: parse_grid(rows) -> (groups, mentors, students, problems).
Вход "rows" — список строк таблицы, каждая строка — список значений ячеек
(str/int/float/None/datetime.date/datetime.datetime — то, что отдаёт
openpyxl, или то же самое после JSON, где дата уже пришла НЕ сырым JS Date,
а строкой 'ГГГГ-ММ-ДД' — см. предупреждение про часовые пояса ниже).

Выходные groups/mentors/students — списки словарей в формате, который прямо
скармливается app.handlers.admin._import_core (там же и живёт upsert-логика,
идемпотентность, сверка группы у ментора/ученика). "_row" в каждой записи —
"строка N" человекочитаемо, N — 1-based номер строки в исходной сетке.

problems — список строк для отчёта админу, с номером строки, где это уместно.
Туда попадают И настоящие проблемы (ученик без группы, ссылка на несуществующую
и т.п. по мере разбора самой сетки), И информационные пометки, которые нужно
обязательно показать человеку: угаданная дата старта группы (см. _parse_meta_row)
и итог по пропущенным пустым строкам.
"""
from __future__ import annotations

import datetime as dt
import re

from app.config import COURSE

# Заголовки колонок внутри блока — сравниваются в нижнем регистре, без
# пробелов по краям. Позиции колонок ищутся per-блок, не хардкодятся.
COL_MENTOR = "ментор"
COL_PHONE = "номер телефона"
COL_NUM = "#"
COL_STUDENT = "ученик"
COL_CONTACTS = "контакты"
COL_SCHOOL = "школа"
COL_CLASS = "класс"
HEADER_KEYS = {COL_MENTOR, COL_PHONE, COL_NUM, COL_STUDENT, COL_CONTACTS, COL_SCHOOL, COL_CLASS}

RU_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
_RU_DATE_RE = re.compile(r"^(\d{1,2})\s+([а-яё]+)$", re.IGNORECASE)

MARKER_SUBSTRING = "настоящие группы"

MAX_PAST_DAYS_BEFORE_NEXT_YEAR = 120


# ------------------------------------------------------------------ мелочи

# Пометка «это справка, а не ошибка». Всё, что начинается с неё,
# отчёт показывает отдельным блоком, не под «Проблемные строки».
INFO_PREFIX = "ℹ️ "


def _cell_text(v) -> str | None:
    """Ячейка -> строка. Числа (Excel/Sheets любят хранить телефон/номер без
    кавычек как число) приводятся аккуратно, без хвоста «.0»."""
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    return s or None


def _is_blank_row(row) -> bool:
    return all(_cell_text(c) is None for c in row)


def _classify_shift(raw) -> str | None:
    if isinstance(raw, dt.time):
        s = raw.strftime("%H:%M")
    else:
        s = str(raw).strip().lower()
    if s in {"утренняя", "утро", "morning"} or s == COURSE["shifts"]["morning"]["start"]:
        return "morning"
    if s in {"вечерняя", "вечер", "evening"} or s == COURSE["shifts"]["evening"]["start"]:
        return "evening"
    return None


def _classify_format(raw) -> str | None:
    s = str(raw).strip().lower()
    if "оффлайн" in s or "офлайн" in s or "offline" in s:
        return "offline"
    if "онлайн" in s or "online" in s:
        return "online"
    return None


def _parse_date_text(s: str) -> tuple[str | None, bool]:
    """Текстовая ячейка -> (ISO-дата или None, угадан_ли_год).

    Порядок попыток: ISO с временем/без (берём только календарную дату, без
    какого-либо пересчёта часового пояса — см. модульный докстринг про
    ловушку с Apps Script/UTC), ДД.ММ.ГГГГ, и, только если года нигде нет,
    русское «27 июля» с эвристикой года (текущий, если получившееся не
    более чем на 120 дней в прошлом, иначе следующий)."""
    s = s.strip()
    if not s:
        return None, False

    # ISO, с временем или без — берём первые 10 символов как календарную дату,
    # никакого сдвига по времени/зоне.
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat(), False
        except ValueError:
            pass

    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat(), False
        except ValueError:
            continue

    m = _RU_DATE_RE.match(s)
    if m:
        day = int(m.group(1))
        month = RU_MONTHS.get(m.group(2).lower())
        if month:
            today = dt.date.today()
            year = today.year
            try:
                candidate = dt.date(year, month, day)
            except ValueError:
                return None, False
            if (today - candidate).days > MAX_PAST_DAYS_BEFORE_NEXT_YEAR:
                candidate = dt.date(year + 1, month, day)
            return candidate.isoformat(), True

    return None, False


def _parse_date_cell(v) -> tuple[str | None, bool, str | None]:
    """Любая ячейка с датой -> (ISO, угадан_ли_год, как выглядело исходное
    значение — для отчёта). Настоящий datetime/date-объект (то, что реально
    отдаёт openpyxl, если в ячейке лежит дата, а не текст) — это ГЛАВНЫЙ,
    точный путь: год там уже есть, гадать не нужно. Угадывание года по
    тексту без года («27 июля») — только запасной путь, на случай, если
    ячейка текстовая."""
    if isinstance(v, dt.datetime):
        return v.date().isoformat(), False, str(v)
    if isinstance(v, dt.date):
        return v.isoformat(), False, str(v)
    s = _cell_text(v)
    if s is None:
        return None, False, None
    iso, guessed = _parse_date_text(s)
    return iso, guessed, s


def _fmt_ru_date(iso: str) -> str:
    return dt.date.fromisoformat(iso).strftime("%d.%m.%Y")


def _combine_class_school(class_raw: str | None, school_raw: str | None) -> str | None:
    parts = []
    if class_raw:
        parts.append(f"{class_raw} класс")
    if school_raw:
        parts.append(school_raw)
    return ", ".join(parts) if parts else None


# ------------------------------------------------------------- строка-маркер

def _is_marker_row(row) -> bool:
    for c in row:
        t = _cell_text(c)
        if not t:
            continue
        norm = re.sub(r"[:\s]+", " ", t.lower()).strip()
        if MARKER_SUBSTRING in norm:
            return True
    return False


# --------------------------------------------------- заголовок колонок блока

def _match_header(row) -> dict[str, int] | None:
    """Строка с названиями колонок блока -> {заголовок: индекс колонки}, либо
    None, если это не она. «Ментор» и «Ученик» обязательны, плюс ещё хотя бы
    один из оставшихся — чтобы случайная строка данных со словом «ментор»
    где-то в тексте не сошла за заголовок."""
    h: dict[str, int] = {}
    for i, c in enumerate(row):
        t = _cell_text(c)
        if t:
            key = t.strip().lower()
            if key in HEADER_KEYS and key not in h:
                h[key] = i
    if COL_MENTOR in h and COL_STUDENT in h and len(h) >= 3:
        return h
    return None


def _phone_col(header: dict[str, int]) -> int | None:
    """Индекс колонки телефона ментора. В шаблоне заголовок «Номер телефона»
    есть всегда, но в реальных блоках он бывает пустым (сама колонка на
    месте, подписи нет) — тогда телефон лежит в колонке сразу справа от
    «Ментор», если её не забрал какой-то другой известный заголовок."""
    if COL_PHONE in header:
        return header[COL_PHONE]
    mentor_idx = header.get(COL_MENTOR)
    if mentor_idx is None:
        return None
    candidate = mentor_idx + 1
    if candidate in header.values():
        return None  # колонка занята другим заголовком — фолбэка нет
    return candidate


def _cell(row, idx: int | None):
    if idx is None or idx >= len(row):
        return None
    return row[idx]


# --------------------------------------------------------- строка-заголовок блока

def _parse_meta_row(row) -> tuple[str | None, str | None, str | None, str | None, bool, list[str]]:
    """Строка перед заголовком колонок -> (название, смена, ISO-дата старта,
    формат online/offline, угадан_ли_год_даты, нераспознанные_значения).
    Название — первая ячейка, которая не опознана ни как смена, ни как дата,
    ни как формат. Всё, что осталось НЕ распознано (кроме самого названия) —
    в последний элемент: скорее всего, опечатка в дате/смене/формате, стоит
    показать админу, а не тихо потерять."""
    name = shift_val = fmt_val = None
    start_iso = None
    guessed = False
    unrecognized: list[str] = []
    for c in row:
        if c is None:
            continue
        if isinstance(c, (dt.date, dt.datetime)):
            iso, g, _src = _parse_date_cell(c)
            if iso:
                start_iso, guessed = iso, g
            continue
        t = _cell_text(c)
        if not t:
            continue
        sh = _classify_shift(t)
        if sh:
            shift_val = sh
            continue
        fmt = _classify_format(t)
        if fmt:
            fmt_val = fmt
            continue
        iso, g = _parse_date_text(t)
        if iso:
            start_iso, guessed = iso, g
            continue
        if name is None:
            name = t
        else:
            unrecognized.append(t)
    return name, shift_val, start_iso, fmt_val, guessed, unrecognized


# ------------------------------------------------------------------- главное

def parse_grid(rows: list[list]) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    groups: list[dict] = []
    mentors: list[dict] = []
    students: list[dict] = []
    problems: list[str] = []

    n = len(rows)

    marker_idx = None
    for i, row in enumerate(rows):
        if _is_marker_row(row):
            marker_idx = i
            break

    if marker_idx is None:
        problems.append(
            "⚠️ строка-маркер «Настоящие группы отсюда:» не найдена — разобрал "
            "всю таблицу целиком (это могло затронуть демонстрационные блоки "
            "«Шаблон»/«Пример», если они есть)."
        )
        start = 0
    else:
        start = marker_idx + 1

    block: dict | None = None
    skipped_rows = 0

    i = start
    while i < n:
        row = rows[i]
        row_num = i + 1

        if _is_blank_row(row):
            block = None
            i += 1
            continue

        header = _match_header(row)
        if header is not None:
            meta_idx = i - 1
            name = shift_val = start_iso = fmt_val = None
            if meta_idx >= start and not _is_blank_row(rows[meta_idx]) \
                    and _match_header(rows[meta_idx]) is None:
                meta_row = rows[meta_idx]
                name, shift_val, start_iso, fmt_val, guessed, unrecognized = _parse_meta_row(meta_row)
                if name and start_iso:
                    # Разрешённая дата — это подтверждение, а не ошибка: она
                    # идёт с пометкой INFO, чтобы отчёт не выглядел проблемным
                    # после каждой успешной синхронизации. Исключение —
                    # угаданный год: вот его нужно перечитать глазами.
                    note = f"строка {meta_idx + 1}: группа «{name}» — старт {_fmt_ru_date(start_iso)}"
                    if guessed:
                        problems.append(note + " (год угадан по правилу 120 дней — проверь!)")
                    else:
                        problems.append(INFO_PREFIX + note)
                for u in unrecognized:
                    problems.append(
                        f"строка {meta_idx + 1}: значение «{u}» в строке-заголовке группы "
                        "не распознано (не смена/дата/формат) — проверь, нет ли опечатки"
                    )
            block = {"name": name, "cols": header}
            if name:
                groups.append({
                    "name": name, "start_date": start_iso, "shift": shift_val,
                    "format": fmt_val, "_row": f"строка {meta_idx + 1}",
                })
            else:
                problems.append(
                    f"строка {row_num}: не нашёл строку-заголовок группы перед шапкой "
                    "колонок — ученики этого блока не будут привязаны к группе"
                )
            i += 1
            continue

        if block is None:
            # Ни разу не встретили шапку колонок после этой строки — скорее
            # всего, это будущая строка-заголовок группы перед ещё не
            # дошедшей шапкой колонок (see _match_header выше, meta_idx
            # смотрит назад) либо мусор. И то и другое молча пропускаем —
            # шапка колонок сама заберёт её как meta-строку, если она ею была.
            i += 1
            continue

        cols = block["cols"]
        mentor_idx = cols.get(COL_MENTOR)
        phone_idx = _phone_col(cols)
        student_idx = cols.get(COL_STUDENT)
        contacts_idx = cols.get(COL_CONTACTS)
        school_idx = cols.get(COL_SCHOOL)
        class_idx = cols.get(COL_CLASS)

        mentor_raw = _cell_text(_cell(row, mentor_idx))
        phone_raw = _cell_text(_cell(row, phone_idx))
        name = _cell_text(_cell(row, student_idx))

        # Ментора забираем ДО проверки имени ученика. В только что заведённом
        # блоке ментор уже вписан, а учеников ещё нет — и терять его нельзя:
        # именно по его номеру бот находит группу, когда ментор заходит.
        if block["name"] is not None:
            if mentor_raw and phone_raw:
                mentors.append({
                    "phone": phone_raw, "full_name": mentor_raw, "group": block["name"],
                    "role": None, "_row": f"строка {row_num}",
                })
            elif mentor_raw or phone_raw:
                problems.append(
                    f"строка {row_num}: у ментора «{mentor_raw or '—'}» не хватает "
                    "имени или телефона — не добавлен"
                )

        if not name:
            skipped_rows += 1
            i += 1
            continue

        if block["name"] is None:
            problems.append(f"строка {row_num}: ученик «{name}» без группы")
            i += 1
            continue

        contacts_raw = _cell_text(_cell(row, contacts_idx))
        school_raw = _cell_text(_cell(row, school_idx))
        class_raw = _cell_text(_cell(row, class_idx))
        students.append({
            "group": block["name"], "full_name": name,
            "class_school": _combine_class_school(class_raw, school_raw),
            "team": None, "phone": contacts_raw, "_row": f"строка {row_num}",
        })
        i += 1

    if skipped_rows:
        # Тоже справка: пустые строки в конце блока — норма, а не поломка.
        problems.append(
            INFO_PREFIX + f"пропущено пустых строк / строк без имени ученика: {skipped_rows}"
        )

    return groups, mentors, students, problems
