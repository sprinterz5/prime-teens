"""Тонкий слой над Postgres. Один пул соединений на процесс, asyncpg.

Схему и миграции владеет Prisma (repo root prisma/schema.prisma,
prisma/migrations/) — общая база с Next.js-платформой (apps/web). Бот сюда
ничего не мигрирует и не создаёт: init() только открывает пул. Имена таблиц/
колонок пришли из старой SQLite-схемы (см. schema.sql — оставлен как
историческая справка) и закреплены в prisma/schema.prisma через @@map/@map,
так что весь SQL ниже работает без изменений в текстах запросов. Реальные
отличия от SQLite — типы: booleans вместо 0/1, BIGINT под Telegram id,
настоящие date/timestamptz вместо TEXT (см. места, где значения приходят из
Postgres уже как datetime.date/datetime, а не строки — например start_date в
group_lesson_window/_group_finished)."""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Optional

import asyncpg

from app.config import COURSE, settings

_pool: Optional[asyncpg.Pool] = None
SCHEMA = Path(__file__).with_name("schema.sql")  # историческая справка, см. файл

# Последний день курса — по нему считаем, завершена ли группа (см. _group_finished).
LAST_DAY_INDEX = max(int(d["index"]) for d in COURSE["days"])


async def _init_connection(conn: asyncpg.Connection) -> None:
    """jsonb/json <-> Python dict/list напрямую, без ручного json.dumps/loads
    на каждом вызывающем месте (см. save_characteristic)."""
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads,
        schema="pg_catalog", format="text",
    )
    await conn.set_type_codec(
        "json", encoder=json.dumps, decoder=json.loads,
        schema="pg_catalog", format="text",
    )


async def init() -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url, min_size=1, max_size=10, init=_init_connection,
        # Windows-сервер embedded-postgres поднимается с client_encoding по
        # умолчанию из локали ОС (WIN1251) — кириллица/эмодзи в параметрах
        # запроса иначе роняют соединение с UntranslatableCharacterError.
        server_settings={"client_encoding": "utf8"},
    )


async def close() -> None:
    if _pool is not None:
        await _pool.close()


def pool() -> asyncpg.Pool:
    assert _pool is not None, "db.init() не вызван"
    return _pool


# ----------------------------- запросы -----------------------------

_PLACEHOLDER = re.compile(r"\?")


def _convert(sql: str) -> str:
    """SQLite-стиль '?' -> asyncpg-стиль '$1'..'$n'. В текстах запросов этого
    модуля '?' нигде не встречается как литерал (только как placeholder),
    так что порядковая замена безопасна."""
    counter = iter(range(1, 10_000))
    return _PLACEHOLDER.sub(lambda _m: f"${next(counter)}", sql)


async def q(sql: str, *args: Any) -> list[asyncpg.Record]:
    return await pool().fetch(_convert(sql), *args)


async def q1(sql: str, *args: Any) -> Optional[asyncpg.Record]:
    return await pool().fetchrow(_convert(sql), *args)


async def run(sql: str, *args: Any) -> int:
    """Выполняет UPDATE/DELETE/INSERT и возвращает число затронутых строк
    (аналог cur.rowcount). Для INSERT, которому нужен id новой/обновлённой
    записи, см. insert_id()."""
    tag = await pool().execute(_convert(sql), *args)
    try:
        return int(tag.split()[-1])
    except (ValueError, IndexError):
        return 0


async def insert_id(sql: str, *args: Any) -> Optional[int]:
    """INSERT (в т.ч. INSERT ... ON CONFLICT DO UPDATE) -> id вставленной/
    обновлённой строки. sql НЕ должен уже содержать RETURNING — эта функция
    сама дописывает ' RETURNING id' и делает fetchval. None — если
    ON CONFLICT DO NOTHING сработал и строка не вставилась."""
    return await pool().fetchval(_convert(sql) + " RETURNING id", *args)


# ----------------------------- телефоны -----------------------------

def norm_phone(raw: str) -> str:
    """+7 (701) 123-45-67 -> 77011234567. 8701... -> 7701..."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits


# ----------------------------- даты -----------------------------

def _to_date(v: Any) -> Optional[dt.date]:
    """ISO-строка/date/datetime -> date для параметра запроса (колонка
    groups.start_date — настоящий DATE в Postgres, asyncpg ждёт datetime.date,
    не строку). Вызывающие места (admin.py, roster_sheet.py) до сих пор
    собирают дату как ISO-строку — конвертация здесь, а не у каждого из них."""
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v))


# ----------------------------- группы -----------------------------

async def upsert_group(name: str, start_date: str | dt.date | None = None,
                       lesson_time: str | None = None, shift: str | None = None,
                       fmt: str | None = None) -> int:
    """fmt — online/offline («Оффлайн/Онлайн» из шапки блока группы в ростере),
    как и остальные необязательные поля тут — обновляется, только если задан
    (пустое/None не затирает то, что уже сохранено)."""
    start = _to_date(start_date)
    row = await q1("SELECT id FROM groups WHERE name = ?", name)
    if row:
        if start:
            await run("UPDATE groups SET start_date = ? WHERE id = ?", start, row["id"])
        if lesson_time:
            await run("UPDATE groups SET lesson_time = ? WHERE id = ?", lesson_time, row["id"])
        if shift:
            await run("UPDATE groups SET shift = ? WHERE id = ?", shift, row["id"])
        if fmt:
            await run("UPDATE groups SET format = ? WHERE id = ?", fmt, row["id"])
        return row["id"]
    return await insert_id(
        "INSERT INTO groups (name, start_date, lesson_time, shift, format) VALUES (?, ?, ?, ?, ?)",
        name, start, lesson_time, shift or "evening", fmt,
    )


async def groups(active_only: bool = True) -> list[asyncpg.Record]:
    """По умолчанию только незавершённые группы (см. _group_finished) — так
    задумано везде, где строится список/кнопки выбора группы: у инлайн-кнопок
    есть лимит, и в куче старых групп нужную не найти. active_only=False —
    вообще все, включая завершённые (например, /groups all)."""
    rows = await q("SELECT * FROM groups ORDER BY name")
    if active_only:
        rows = [g for g in rows if not await _group_finished(g)]
    return rows


async def group(group_id: int) -> Optional[asyncpg.Record]:
    return await q1("SELECT * FROM groups WHERE id = ?", group_id)


def _day_by_index(day_index: int) -> Optional[dict]:
    return next((d for d in COURSE["days"] if d["index"] == day_index), None)


def _lesson_start_hm(group_row, day: dict) -> tuple[int, int]:
    """Приоритет начала занятия: start_override дня -> ручной lesson_time
    группы -> время смены группы (shifts в course.yaml)."""
    raw = day.get("start_override") or group_row["lesson_time"] or \
        COURSE["shifts"][group_row["shift"] or "evening"]["start"]
    hh, mm = str(raw).split(":")
    return int(hh), int(mm)


def _block_span(block) -> int:
    """Сколько слотов занимает блок. Строка и null — один, словарь с span —
    сколько указано: «Исследования» идут два блока подряд, там и про
    исследовательские программы."""
    if isinstance(block, dict):
        return max(1, int(block.get("span", 1)))
    return 1


def _block_name(block) -> str | None:
    return block.get("name") if isinstance(block, dict) else block


def _slot_starts(day: dict) -> list[int] | None:
    """Начала слотов в минутах от начала занятия, если шаг неровный
    (будни: 19:00 / 20:00 / 20:50). Свой шаг дня (block_step_minutes, выходные)
    важнее общего списка; None — считать равным шагом."""
    if day.get("slot_starts_minutes"):
        return [int(m) for m in day["slot_starts_minutes"]]
    if day.get("block_step_minutes") or day.get("duration_minutes"):
        return None
    starts = COURSE.get("slot_starts_minutes")
    return [int(m) for m in starts] if starts else None


def _lesson_duration_minutes(day: dict) -> int:
    """duration_minutes дня, если задан; при неровных слотах — общий
    lesson_minutes; иначе (число слотов в blocks) × шаг.
    Пустые (null) слоты и span-блоки считаются по занятым слотам."""
    if day.get("duration_minutes"):
        return int(day["duration_minutes"])
    if _slot_starts(day) is not None and COURSE.get("lesson_minutes"):
        return int(COURSE["lesson_minutes"])
    step = int(day.get("block_step_minutes") or COURSE["block_step_minutes"])
    slots = sum(_block_span(b) for b in (day.get("blocks") or []))
    return slots * step


async def group_lesson_window(group_id: int, day_index: int) -> Optional[tuple[dt.datetime, dt.datetime]]:
    """Начало и конец занятия = start_date группы + offset_days дня, время и
    длительность — по правилам смен (см. _lesson_start_hm/_lesson_duration_minutes)."""
    g = await group(group_id)
    if not g or not g["start_date"]:
        return None
    day = _day_by_index(day_index)
    if not day:
        return None
    start_date = g["start_date"]  # уже datetime.date — колонка groups.start_date типа DATE
    date = start_date + dt.timedelta(days=int(day["offset_days"]))
    hh, mm = _lesson_start_hm(g, day)
    start = dt.datetime(date.year, date.month, date.day, hh, mm, tzinfo=settings.tz)
    end = start + dt.timedelta(minutes=_lesson_duration_minutes(day))
    return start, end


async def group_lesson_datetime(group_id: int, day_index: int) -> Optional[dt.datetime]:
    """Дата и время начала занятия. См. group_lesson_window для конца и длительности."""
    window = await group_lesson_window(group_id, day_index)
    return window[0] if window else None


async def _group_finished(g: asyncpg.Record) -> bool:
    """Группа считается завершённой, когда конец последнего дня курса
    (LAST_DAY_INDEX, сейчас день 9 — хакатон) уже в прошлом. Группа без
    start_date ещё не начата — не завершена. Никакого отдельного флага в
    БД: чистое вычисление по датам, см. groups()/mentor_groups()."""
    if not g["start_date"]:
        return False
    window = await group_lesson_window(g["id"], LAST_DAY_INDEX)
    if window is None:
        return False
    return window[1] < dt.datetime.now(settings.tz)


def day_block_times(day: dict, start: dt.datetime) -> list[tuple[dt.datetime, dt.datetime, str]]:
    """Список (начало, конец, название) для непустых блоков дня.

    Пустые (null) слоты в выводе пропускаются, но время под них учитывается —
    они сдвигают следующий блок. Блок со span занимает несколько слотов подряд:
    так «Исследования» показываются как 10:00–11:40, а не как час плюс дырка."""
    step = int(day.get("block_step_minutes") or COURSE["block_step_minutes"])
    starts = _slot_starts(day)
    total = _lesson_duration_minutes(day)

    slots = sum(_block_span(b) for b in (day.get("blocks") or []))

    def at(i: int) -> int:
        # Начало i-го слота; за последним слотом — конец занятия.
        if i >= slots:
            return total
        if starts is None:
            return i * step
        return starts[i] if i < len(starts) else total

    out: list[tuple[dt.datetime, dt.datetime, str]] = []
    slot = 0
    for block in day.get("blocks") or []:
        span = _block_span(block)
        name = _block_name(block)
        if name:
            out.append((start + dt.timedelta(minutes=at(slot)), start + dt.timedelta(minutes=at(slot + span)), name))
        slot += span
    return out


def fmt_block(t0: dt.datetime, t1: dt.datetime, name: str) -> str:
    """«10:00 Дебаты» для обычного блока, «10:00–11:40 Исследования» для длинного."""
    head = t0.strftime("%H:%M")
    if (t1 - t0) > dt.timedelta(minutes=int(COURSE["block_minutes"]) + 20):
        head += "–" + t1.strftime("%H:%M")
    return f"{head} {name}"


# ----------------------------- ученики -----------------------------

async def add_student(group_id: int, full_name: str, class_school: str | None = None,
                      team: str | None = None, phone: str | None = None) -> int:
    parts = full_name.split()
    short = parts[-1] if parts else full_name
    # Нормализуем здесь, а не полагаемся на то, что каждый вызывающий не
    # забудет это сделать сам: students.phone теперь ещё и ключ поиска для
    # детского бота (students_by_phone), несовпадающий формат — тихий отказ
    # найти человека, а не ошибка, которую сразу заметишь.
    if phone:
        phone = norm_phone(phone)
    await run(
        """INSERT INTO students (group_id, full_name, short_name, class_school, team, phone)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(group_id, full_name) DO UPDATE SET
             class_school = COALESCE(excluded.class_school, students.class_school),
             team         = COALESCE(excluded.team, students.team),
             phone        = COALESCE(excluded.phone, students.phone)""",
        group_id, full_name, short, class_school, team, phone,
    )
    row = await q1("SELECT id FROM students WHERE group_id = ? AND full_name = ?",
                   group_id, full_name)
    return row["id"]


async def students(group_id: int, active_only: bool = True) -> list[asyncpg.Record]:
    sql = "SELECT * FROM students WHERE group_id = ?"
    if active_only:
        sql += " AND active"
    return await q(sql + " ORDER BY full_name", group_id)


async def student(student_id: int) -> Optional[asyncpg.Record]:
    return await q1("SELECT * FROM students WHERE id = ?", student_id)


# ----------------------------- детский бот: привязка аккаунта -----------------------------

async def student_by_tg(tg_user_id: int) -> Optional[asyncpg.Record]:
    return await q1("SELECT * FROM students WHERE tg_user_id = ?", tg_user_id)


async def students_by_phone(phone: str) -> list[asyncpg.Record]:
    """Активные ученики с таким номером — обычно один, но телефон бывает
    семейным (номер родителя на двоих детей), поэтому список, а не одна
    запись: вызывающий код должен уметь предложить выбор."""
    return await q(
        "SELECT * FROM students WHERE phone = ? AND active ORDER BY full_name",
        norm_phone(phone),
    )


async def link_student_tg(student_id: int, tg_user_id: int, phone: str | None = None) -> None:
    """Привязывает Telegram-аккаунт к ученику. phone — только если у ученика
    его ещё не было (номер из ростера, если он там был, не затираем)."""
    await run("UPDATE students SET tg_user_id = ? WHERE id = ?", tg_user_id, student_id)
    if phone:
        await run("UPDATE students SET phone = COALESCE(phone, ?) WHERE id = ?",
                  norm_phone(phone), student_id)


# ----------------------------- детский бот: отзывы о занятии -----------------------------
#
# Анонимно ПО ПОЛИТИКЕ: student_id хранится (нужен для «уже ответил сегодня»
# и на случай, если правило анонимности когда-нибудь пересмотрят), но
# group_kid_feedback() ниже — единственный читающий запрос для менторов/
# админа — намеренно не выбирает full_name и ни с чем его не связывает.

async def save_kid_feedback(student_id: int, group_id: int, day_index: int,
                            rating: int | None, text: str | None, source: str) -> int:
    """Один отзыв на (ученик, день) — повторная отправка за тот же день
    заменяет прежнюю, а не плодит дубли."""
    await run(
        "DELETE FROM kid_feedback WHERE student_id = ? AND day_index = ?",
        student_id, day_index,
    )
    return await insert_id(
        """INSERT INTO kid_feedback (student_id, group_id, day_index, rating, text, source)
           VALUES (?, ?, ?, ?, ?, ?)""",
        student_id, group_id, day_index, rating, text, source,
    )


async def kid_feedback_done(student_id: int, day_index: int) -> bool:
    return (await q1("SELECT 1 FROM kid_feedback WHERE student_id = ? AND day_index = ?",
                     student_id, day_index)) is not None


async def group_kid_feedback(group_id: int, day_index: int | None = None) -> list[asyncpg.Record]:
    """Для менторов/админа: отзывы без имени ученика — только день, оценка,
    текст. Столбца full_name в выборке нет намеренно, см. докстринг выше."""
    sql = "SELECT day_index, rating, text, source, created_at FROM kid_feedback WHERE group_id = ?"
    args: list[Any] = [group_id]
    if day_index is not None:
        sql += " AND day_index = ?"
        args.append(day_index)
    return await q(sql + " ORDER BY day_index, created_at", *args)


async def kid_feedback_stats(group_id: int) -> dict[int, dict]:
    """По каждому дню: сколько отзывов и средняя оценка (без текста и без
    ученика — только числа, для сводки /overview у админа)."""
    rows = await q(
        # AVG(integer) в Postgres -> numeric (decimal.Decimal), а не float,
        # как у SQLite — ::float8 возвращает тот же тип, что и раньше.
        """SELECT day_index, COUNT(*) AS n, AVG(rating)::float8 AS avg_rating
           FROM kid_feedback WHERE group_id = ? GROUP BY day_index""",
        group_id,
    )
    return {r["day_index"]: {"count": r["n"], "avg": r["avg_rating"]} for r in rows}


# ----------------------------- детский бот: команды на хакатон -----------------------------
#
# Заполняются самими учениками (капитан создаёт, остальные присоединяются по
# ссылке-коду) — это и есть заполнение students.team в менторской базе, без
# ручного ввода составов админом. Кросс-групповые команды разрешены сейчас
# намеренно (см. обсуждение с заказчиком) — сузить до одной группы можно
# будет отдельной правкой, тронув только join_hack_team.

async def hack_team_of_student(student_id: int) -> Optional[asyncpg.Record]:
    return await q1(
        """SELECT t.* FROM hack_teams t
           JOIN hack_team_members m ON m.team_id = t.id
           WHERE m.student_id = ?""",
        student_id,
    )


async def hack_team_by_code(join_code: str) -> Optional[asyncpg.Record]:
    return await q1("SELECT * FROM hack_teams WHERE join_code = ?", join_code)


async def hack_team_members(team_id: int) -> list[asyncpg.Record]:
    return await q(
        """SELECT s.* FROM students s
           JOIN hack_team_members m ON m.student_id = s.id
           WHERE m.team_id = ? ORDER BY m.joined_at""",
        team_id,
    )


async def _sync_student_team(student_id: int, team_name: str | None) -> None:
    """Пишет имя команды в students.team — оттуда его читает менторский
    опрос по хакатону (app/flow.py: build_steps('hackathon', ...))."""
    await run("UPDATE students SET team = ? WHERE id = ?", team_name, student_id)


async def create_hack_team(name: str, case_name: str | None, leader_id: int,
                           join_code: str) -> int:
    team_id = await insert_id(
        "INSERT INTO hack_teams (name, case_name, leader_id, join_code) VALUES (?, ?, ?, ?)",
        name, case_name, leader_id, join_code,
    )
    await run("INSERT INTO hack_team_members (team_id, student_id) VALUES (?, ?)",
              team_id, leader_id)
    await _sync_student_team(leader_id, name)
    return team_id


async def join_hack_team(team_id: int, student_id: int) -> None:
    await run(
        "INSERT INTO hack_team_members (team_id, student_id) VALUES (?, ?) "
        "ON CONFLICT (team_id, student_id) DO NOTHING",
        team_id, student_id,
    )
    team = await q1("SELECT name FROM hack_teams WHERE id = ?", team_id)
    if team:
        await _sync_student_team(student_id, team["name"])


async def leave_hack_team(student_id: int) -> None:
    await run("DELETE FROM hack_team_members WHERE student_id = ?", student_id)
    await _sync_student_team(student_id, None)


# ----------------------------- менторы -----------------------------

async def roster_lookup(phone: str) -> Optional[asyncpg.Record]:
    return await q1("SELECT * FROM roster WHERE phone = ?", norm_phone(phone))


async def add_to_roster(phone: str, full_name: str, group_id: int | None,
                        is_admin: bool = False, is_mentor: bool = True) -> None:
    await run(
        """INSERT INTO roster (phone, full_name, group_id, is_admin, is_mentor)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(phone) DO UPDATE SET
             full_name = excluded.full_name,
             group_id  = excluded.group_id,
             is_admin  = excluded.is_admin,
             is_mentor = excluded.is_mentor""",
        norm_phone(phone), full_name, group_id, bool(is_admin), bool(is_mentor),
    )


async def is_first_run() -> bool:
    """Ни одного ментора и пустой белый список — бот только что развёрнут.
    В этот момент первый, кто представится, становится администратором:
    иначе получается замкнутый круг (чтобы попасть в ADMIN_IDS, нужен свой
    Telegram ID, а узнать его можно только у работающего бота)."""
    return (await q1("SELECT 1 FROM mentors LIMIT 1")) is None \
        and (await q1("SELECT 1 FROM roster LIMIT 1")) is None


async def set_admin(tg_user_id: int, value: bool = True) -> bool:
    n = await run("UPDATE mentors SET is_admin = ? WHERE tg_user_id = ?",
                  bool(value), tg_user_id)
    return n > 0


async def set_mentor(tg_user_id: int, value: bool = True) -> bool:
    n = await run("UPDATE mentors SET is_mentor = ? WHERE tg_user_id = ?",
                  bool(value), tg_user_id)
    return n > 0


async def mentor_by_phone(phone: str) -> Optional[asyncpg.Record]:
    return await q1("SELECT * FROM mentors WHERE phone = ?", norm_phone(phone))


async def mentor_by_tg(tg_user_id: int) -> Optional[asyncpg.Record]:
    return await q1("SELECT * FROM mentors WHERE tg_user_id = ?", tg_user_id)


async def register_mentor(tg_user_id: int, phone: str, full_name: str,
                          is_admin: bool = False, is_mentor: bool = True) -> int:
    """is_admin/is_mentor независимы и только «добавляются»: GREATEST с уже
    сохранённым значением (Postgres-эквивалент SQLite-шного многоаргументного
    MAX(); булевы false < true, так что это ИЛИ) — повторная регистрация
    (например, по ссылке администратора) никогда не отбирает роль, выданную
    раньше."""
    await run(
        """INSERT INTO mentors (tg_user_id, phone, full_name, is_admin, is_mentor)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(tg_user_id) DO UPDATE SET
             phone     = excluded.phone,
             full_name = excluded.full_name,
             is_admin  = GREATEST(mentors.is_admin, excluded.is_admin),
             is_mentor = GREATEST(mentors.is_mentor, excluded.is_mentor)""",
        tg_user_id, norm_phone(phone), full_name, bool(is_admin), bool(is_mentor),
    )
    row = await q1("SELECT id FROM mentors WHERE tg_user_id = ?", tg_user_id)
    return row["id"]


async def link_mentor_group(mentor_id: int, group_id: int) -> None:
    await run(
        "INSERT INTO mentor_groups (mentor_id, group_id) VALUES (?, ?) "
        "ON CONFLICT (mentor_id, group_id) DO NOTHING",
        mentor_id, group_id,
    )


async def mentor_groups(mentor_id: int, active_only: bool = True) -> list[asyncpg.Record]:
    """См. groups(): по умолчанию ментор видит только свои незавершённые группы."""
    rows = await q(
        """SELECT g.* FROM groups g
           JOIN mentor_groups mg ON mg.group_id = g.id
           WHERE mg.mentor_id = ? ORDER BY g.name""",
        mentor_id,
    )
    if active_only:
        rows = [g for g in rows if not await _group_finished(g)]
    return rows


async def group_mentors(group_id: int) -> list[asyncpg.Record]:
    """Только действующие менторы группы (is_mentor=true) — админ-организатор,
    который лишь привязан административно, сюда не попадает."""
    return await q(
        """SELECT m.* FROM mentors m
           JOIN mentor_groups mg ON mg.mentor_id = m.id
           WHERE mg.group_id = ? AND m.is_mentor""",
        group_id,
    )


async def all_mentor_group_pairs() -> list[asyncpg.Record]:
    return await q(
        """SELECT m.id AS mentor_id, m.tg_user_id, m.full_name AS mentor_name,
                  g.id AS group_id, g.name AS group_name, g.start_date
           FROM mentor_groups mg
           JOIN mentors m ON m.id = mg.mentor_id
           JOIN groups  g ON g.id = mg.group_id
           WHERE g.start_date IS NOT NULL AND m.is_mentor"""
    )


# ----------------------------- сессии и ответы -----------------------------

async def open_session(mentor_id: int, group_id: int, day_index: int,
                       kind: str = "lesson") -> int:
    row = await q1(
        """SELECT id FROM sessions
           WHERE mentor_id = ? AND group_id = ? AND day_index = ?
             AND kind = ? AND status = 'open'""",
        mentor_id, group_id, day_index, kind,
    )
    if row:
        return row["id"]
    return await insert_id(
        "INSERT INTO sessions (mentor_id, group_id, day_index, kind) VALUES (?, ?, ?, ?)",
        mentor_id, group_id, day_index, kind,
    )


async def finish_session(session_id: int) -> None:
    await run(
        "UPDATE sessions SET status = 'done', finished_at = now() WHERE id = ?",
        session_id,
    )


async def session_done(group_id: int, day_index: int, kind: str = "lesson") -> bool:
    row = await q1(
        """SELECT 1 FROM sessions
           WHERE group_id = ? AND day_index = ? AND kind = ? AND status = 'done' LIMIT 1""",
        group_id, day_index, kind,
    )
    return row is not None


async def save_answer(session_id: int, group_id: int, day_index: int,
                      question_key: str, question_text: str, maps_to: str | None,
                      student_id: int | None, value: str | None, text: str | None,
                      source: str) -> int:
    return await insert_id(
        """INSERT INTO answers
             (session_id, group_id, day_index, student_id, question_key,
              question_text, maps_to, value, text, source)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        session_id, group_id, day_index, student_id, question_key,
        question_text, maps_to, value, text, source,
    )


async def update_answer(answer_id: int, text: str | None, source: str) -> None:
    """Перезаписать уже сохранённый ответ — кнопка «Переписать»."""
    await run("UPDATE answers SET text = ?, source = ? WHERE id = ?",
              text, source, answer_id)


async def answer(answer_id: int) -> Optional[asyncpg.Record]:
    return await q1("SELECT * FROM answers WHERE id = ?", answer_id)


async def student_answers(student_id: int) -> list[asyncpg.Record]:
    return await q(
        "SELECT * FROM answers WHERE student_id = ? ORDER BY day_index, id", student_id
    )


async def group_answers(group_id: int) -> list[asyncpg.Record]:
    return await q(
        "SELECT * FROM answers WHERE group_id = ? AND student_id IS NULL ORDER BY day_index, id",
        group_id,
    )


# Ключи, которые считаются «эпизодом» — конкретным фактом про ученика.
# Именно их количество определяет, готова ли характеристика.
EPISODE_KEYS = ("episode", "spotlight_episode", "last_episode", "hack_win")


async def episode_counts(group_id: int) -> dict[int, int]:
    marks = ",".join("?" * len(EPISODE_KEYS))
    rows = await q(
        f"""SELECT student_id, COUNT(*) AS c FROM answers
            WHERE group_id = ? AND student_id IS NOT NULL
              AND question_key IN ({marks})
              AND text IS NOT NULL AND TRIM(text) <> ''
            GROUP BY student_id""",
        group_id, *EPISODE_KEYS,
    )
    return {r["student_id"]: r["c"] for r in rows}


async def spotlight_counts(group_id: int) -> dict[int, int]:
    rows = await q(
        """SELECT student_id, COUNT(*) AS c FROM answers
           WHERE group_id = ? AND question_key = 'spotlight_mode'
             AND student_id IS NOT NULL
           GROUP BY student_id""",
        group_id,
    )
    return {r["student_id"]: r["c"] for r in rows}


async def tag_counts(student_id: int) -> dict[str, int]:
    rows = await q(
        """SELECT value, COUNT(*) AS c FROM answers
           WHERE student_id = ? AND question_key IN ('standout_tags', 'struggled_tags')
             AND value IS NOT NULL AND value <> ''
           GROUP BY value""",
        student_id,
    )
    return {r["value"]: r["c"] for r in rows}


async def axis_value(student_id: int, axis_code: str, kind: str) -> Optional[int]:
    """Оценка по оси из стартового (kind='baseline') или финального замера."""
    row = await q1(
        """SELECT a.value FROM answers a
           JOIN sessions s ON s.id = a.session_id
           WHERE a.student_id = ? AND a.question_key = ? AND s.kind = ?
           ORDER BY a.id DESC LIMIT 1""",
        student_id, f"axis_{axis_code}", kind,
    )
    if row and row["value"] is not None and str(row["value"]).lstrip("-").isdigit():
        return int(row["value"])
    return None


async def answers_count(session_id: int) -> int:
    row = await q1("SELECT COUNT(*) AS c FROM answers WHERE session_id = ?", session_id)
    return row["c"] if row else 0


# ----------------------------- характеристики -----------------------------

async def save_characteristic(student_id: int, payload: Any, html_path: str) -> int:
    """payload — Python-объект (dict/list из llm.generate), не строка: пул
    настроен на jsonb-кодек (см. _init_connection), сериализация/десериализация
    симметричны и происходят на границе asyncpg, а не у каждого вызывающего."""
    return await insert_id(
        "INSERT INTO characteristics (student_id, payload, html_path) VALUES (?, ?, ?)",
        student_id, payload, html_path,
    )


async def latest_characteristic(student_id: int) -> Optional[asyncpg.Record]:
    return await q1(
        "SELECT * FROM characteristics WHERE student_id = ? ORDER BY id DESC LIMIT 1",
        student_id,
    )


# ----------------------------- приглашения -----------------------------
#
# Все ссылки одноразовые: used_by_tg/used_at ставятся при первом
# использовании, дальше её отвергают, кроме повторного захода того же
# used_by_tg (это не ошибка — просто открыть свой обычный экран заново).
#
# Менторская ссылка (role='mentor') — просто одноразовый пропуск в бота, БЕЗ
# привязки к группе. group_id у такой записи ничего не значит и никогда не
# читается при регистрации (см. handlers/registration.py:start_invite/
# got_contact) — исторически колонка NOT NULL с FK на groups(id), поэтому
# при создании такой ссылки туда пишется первая попавшаяся группа (см.
# handlers/admin.py:_placeholder_group_id), просто чтобы удовлетворить
# ограничение. Реальную группу ментор получает по своему номеру телефона из
# roster (заполняется Excel-импортом или /add_mentor) — см. _link_mentor_
# from_roster в registration.py.
#
# Ссылка администратора (role='admin') устроена так же: group_id тоже ничего
# не значит. Персональная ссылка ученика (student_id задан) — единственная,
# где group_id используется по назначению.

async def create_invite(token: str, group_id: int, created_by: int | None,
                        role: str = "mentor", student_id: int | None = None) -> None:
    await run(
        "INSERT INTO invites (token, group_id, student_id, created_by, role) "
        "VALUES (?, ?, ?, ?, ?)",
        token, group_id, student_id, created_by, role,
    )


async def invite_by_token(token: str) -> Optional[asyncpg.Record]:
    return await q1("SELECT * FROM invites WHERE token = ?", token)


async def active_invite(token: str) -> Optional[asyncpg.Record]:
    """Только не отозванная ссылка — то, что реально пускает регистрацию."""
    return await q1("SELECT * FROM invites WHERE token = ? AND NOT revoked", token)


async def revoke_invite(token: str) -> bool:
    n = await run("UPDATE invites SET revoked = true WHERE token = ?", token)
    return n > 0


async def group_invites(group_id: int) -> list[asyncpg.Record]:
    return await q("SELECT * FROM invites WHERE group_id = ? ORDER BY created_at DESC", group_id)


async def active_student_invite(student_id: int) -> Optional[asyncpg.Record]:
    """Ещё не использованная и не отозванная персональная ссылка ученика —
    чтобы повторный вызов «Ссылки для учеников» не плодил новые токены на
    того же человека."""
    return await q1(
        "SELECT * FROM invites WHERE student_id = ? AND NOT revoked AND used_by_tg IS NULL "
        "ORDER BY created_at DESC LIMIT 1",
        student_id,
    )


def _one_time(invite: asyncpg.Record) -> bool:
    """Все ссылки одноразовые. Раньше групповая ссылка ментора (role='mentor',
    student_id NULL) была многоразовой — с переходом на Excel-импорт
    менторская ссылка стала просто одноразовым пропуском в бота (группа
    определяется по телефону из roster, а не по ссылке), так что
    многоразовых ссылок в системе больше не осталось вовсе. Статус 'multi' в
    _invite_status/invite_status ниже теперь недостижим, но оставлен —
    дешевле, чем вычищать по всем вызывающим."""
    return True


def _invite_status(invite: Optional[asyncpg.Record], tg_user_id: int) -> str:
    if invite is None:
        return "not_found"
    if invite["revoked"]:
        return "revoked"
    if not _one_time(invite):
        return "multi"
    if invite["used_by_tg"] is None:
        return "ok"
    return "used_by_self" if invite["used_by_tg"] == tg_user_id else "used_by_other"


async def invite_status(token: str, tg_user_id: int) -> str:
    """Смотрит на ссылку, ничего не меняет. Один из:
    not_found | revoked | used_by_other | used_by_self | multi | ok
    ('ok' — одноразовая и ещё свободна; 'multi' — многоразовая групповая)."""
    return _invite_status(await invite_by_token(token), tg_user_id)


async def claim_invite(token: str, tg_user_id: int) -> str:
    """Пытается использовать одноразовую ссылку — тот же набор статусов, что
    invite_status. 'ok' означает, что ссылка была свободна и только что
    помечена использованной этим tg_user_id. Многоразовую групповую ссылку
    не трогает (статус 'multi'), звать эту функцию для неё не обязательно."""
    invite = await invite_by_token(token)
    status = _invite_status(invite, tg_user_id)
    if status != "ok":
        return status
    n = await run(
        "UPDATE invites SET used_by_tg = ?, used_at = now() "
        "WHERE token = ? AND used_by_tg IS NULL",
        tg_user_id, token,
    )
    if n == 0:
        # кто-то успел использовать её первым между чтением и записью
        return _invite_status(await invite_by_token(token), tg_user_id)
    return "ok"


# ----------------------------- дедупликация уведомлений -----------------------------

async def mark_sent(key: str) -> bool:
    """True — если это первая отправка (значит, можно слать)."""
    try:
        await run("INSERT INTO notifications (key) VALUES (?)", key)
        return True
    except Exception:
        return False


# ----------------------------- realtime (веб-платформа) -----------------------------

async def notify_workbook(payload: dict) -> None:
    """pg_notify на тот же канал 'workbook', что слушает lib/realtime.ts —
    так изменения, сделанные ботом (пока только архивация потока, см.
    scheduler.archive_lock), долетают до открытых вкладок тетради живьём,
    без перезагрузки. Ключи payload — camelCase (studentId/groupId/...),
    как их ждёт JSON.parse на стороне Next.js/клиента; держите форму в
    синхроне с WorkbookNotification в lib/realtime.ts."""
    await pool().execute("SELECT pg_notify('workbook', $1)", json.dumps(payload))
