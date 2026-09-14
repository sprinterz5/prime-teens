"""Разовый перенос данных из старой SQLite-базы бота (aiosqlite-эпоха) в
Postgres:

    python -m tools.sqlite_to_pg [путь/к/бот.sqlite3] [--database-url URL] [--dry-run]

Путь по умолчанию — data/bot.sqlite3 (относительно bot/). Без --database-url
пишет в DATABASE_URL из .env (app/config.py) — то есть в БОЕВУЮ primeteens,
так что для боевого переноса просто запусти без флагов; для прогона на
тестовой базе передай --database-url явно (см. отчёт агента — реальный запуск
делался только с --database-url на primeteens_test).

Конвертирует типы под новую Postgres-схему (см. prisma/schema.prisma):
  - 0/1 (INTEGER) -> boolean: active, is_admin, is_mentor, revoked;
  - ISO-текст -> date/timestamptz: start_date, created_at, started_at,
    finished_at, used_at, joined_at, sent_at;
  - characteristics.payload (JSON-текст) -> jsonb (::jsonb на вставке).

Сохраняет id как есть (важно: FK между таблицами ссылаются именно на них),
после переноса выставляет sequence каждой serial-колонки на MAX(id)+1.
Идемпотентно: ON CONFLICT DO NOTHING по настоящему первичному ключу таблицы —
повторный запуск на той же или подросшей sqlite-базе не плодит дублей и не
падает на уже перенесённых строках.

--dry-run печатает только количество строк на таблицу в sqlite и в Postgress
(до переноса) — НИКОГДА не печатает имена/телефоны/тексты ответов, только
числа и id.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable, Optional

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # bot/ -> import app.*

from app.config import settings  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


# ----------------------------------------------------------------- парсинг значений

def _to_bool(v: Any) -> Optional[bool]:
    return None if v is None else bool(v)


def _to_date(v: Any) -> Optional[dt.date]:
    if v is None:
        return None
    if isinstance(v, dt.date):
        return v
    s = str(v).strip()
    return dt.date.fromisoformat(s[:10]) if s else None


def _to_timestamp(v: Any) -> Optional[dt.datetime]:
    """SQLite datetime('now') -> 'YYYY-MM-DD HH:MM:SS', UTC, наивная строка.
    Отдаём tz-aware UTC — Postgres TIMESTAMPTZ хранит абсолютный момент,
    двусмысленности без tzinfo лучше не оставлять."""
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v if v.tzinfo else v.replace(tzinfo=dt.timezone.utc)
    s = str(v).strip()
    if not s:
        return None
    s = s.replace(" ", "T", 1) if ("T" not in s and " " in s) else s
    d = dt.datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _identity(v: Any) -> Any:
    return v


# ----------------------------------------------------------------- описание таблиц
#
# Порядок — по зависимостям FK (родители раньше детей). "pk" — реальный
# первичный/уникальный ключ в Postgres для ON CONFLICT ... DO NOTHING.
# "convert" — {колонка: функция(значение_из_sqlite)}; колонки, которых нет в
# конкретном sqlite-файле (старый бэкап), просто пропускаются — Postgres
# подставит свой DEFAULT/NULL. "serial" — есть ли автоинкрементный id
# (нужно после переноса выставить sequence).

TableSpec = dict


TABLES: list[TableSpec] = [
    dict(name="groups", pk=["id"], serial=True, convert={
        "start_date": _to_date, "created_at": _to_timestamp,
    }),
    dict(name="roster", pk=["phone"], serial=False, convert={
        "is_admin": _to_bool, "is_mentor": _to_bool,
    }),
    dict(name="mentors", pk=["id"], serial=True, convert={
        "is_admin": _to_bool, "is_mentor": _to_bool, "created_at": _to_timestamp,
    }),
    dict(name="students", pk=["id"], serial=True, convert={
        "active": _to_bool,
    }),
    dict(name="mentor_groups", pk=["mentor_id", "group_id"], serial=False, convert={}),
    dict(name="sessions", pk=["id"], serial=True, convert={
        "started_at": _to_timestamp, "finished_at": _to_timestamp,
    }),
    dict(name="answers", pk=["id"], serial=True, convert={
        "created_at": _to_timestamp,
    }),
    dict(name="characteristics", pk=["id"], serial=True, convert={
        "created_at": _to_timestamp,
    }, jsonb_cols={"payload"}),
    dict(name="hack_teams", pk=["id"], serial=True, convert={
        "created_at": _to_timestamp,
    }),
    dict(name="hack_team_members", pk=["team_id", "student_id"], serial=False, convert={
        "joined_at": _to_timestamp,
    }),
    dict(name="kid_feedback", pk=["id"], serial=True, convert={
        "created_at": _to_timestamp,
    }),
    dict(name="invites", pk=["token"], serial=False, convert={
        "revoked": _to_bool, "created_at": _to_timestamp, "used_at": _to_timestamp,
    }),
    dict(name="notifications", pk=["key"], serial=False, convert={
        "sent_at": _to_timestamp,
    }),
]


def _sqlite_columns(sconn: sqlite3.Connection, table: str) -> list[str]:
    try:
        return [r[1] for r in sconn.execute(f"PRAGMA table_info({table})")]
    except sqlite3.OperationalError:
        return []


def _sqlite_table_exists(sconn: sqlite3.Connection, table: str) -> bool:
    row = sconn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


async def _reset_sequence(pconn: asyncpg.Connection, table: str) -> None:
    await pconn.execute(
        "SELECT setval(pg_get_serial_sequence($1, 'id'), "
        "COALESCE((SELECT MAX(id) FROM " + f'"{table}"' + "), 0) + 1, false)",
        table,
    )


async def migrate_table(sconn: sqlite3.Connection, pconn: asyncpg.Connection,
                        spec: TableSpec, dry_run: bool) -> tuple[int, int, int]:
    """Возвращает (в_sqlite, было_в_postgres, добавлено)."""
    table = spec["name"]
    if not _sqlite_table_exists(sconn, table):
        return 0, 0, 0

    cols = _sqlite_columns(sconn, table)
    if not cols:
        return 0, 0, 0

    src_rows = sconn.execute(f"SELECT {', '.join(cols)} FROM {table}").fetchall()
    total_sqlite = len(src_rows)

    before = await pconn.fetchval(f'SELECT COUNT(*) FROM "{table}"')

    if dry_run or not src_rows:
        return total_sqlite, before, 0

    convert: dict[str, Callable] = spec["convert"]
    jsonb_cols: set[str] = spec.get("jsonb_cols", set())

    placeholders = []
    for i, c in enumerate(cols, start=1):
        placeholders.append(f"${i}::jsonb" if c in jsonb_cols else f"${i}")
    col_list = ", ".join(f'"{c}"' for c in cols)
    conflict_cols = ", ".join(f'"{c}"' for c in spec["pk"])
    sql = (
        f'INSERT INTO "{table}" ({col_list}) VALUES ({", ".join(placeholders)}) '
        f"ON CONFLICT ({conflict_cols}) DO NOTHING"
    )

    values: list[tuple] = []
    for row in src_rows:
        rec = []
        for c in cols:
            v = row[c]
            fn = convert.get(c, _identity)
            rec.append(fn(v))
        values.append(tuple(rec))

    await pconn.executemany(sql, values)

    after = await pconn.fetchval(f'SELECT COUNT(*) FROM "{table}"')
    if spec["serial"]:
        await _reset_sequence(pconn, table)
    return total_sqlite, before, after - before


async def run(sqlite_path: Path, database_url: str, dry_run: bool) -> None:
    if not sqlite_path.exists():
        print(f"Нет файла: {sqlite_path}")
        sys.exit(1)

    # Открываем на чтение; WAL/-shm рядом (если есть) подхватываются сами.
    sconn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    sconn.row_factory = sqlite3.Row

    pconn = await asyncpg.connect(dsn=database_url, server_settings={"client_encoding": "utf8"})
    try:
        print(f"источник:  {sqlite_path}")
        print(f"назначение: {database_url.split('@')[-1]}")  # без логина/пароля
        print(f"режим:     {'dry-run (ничего не пишу)' if dry_run else 'перенос'}\n")

        rows_fmt = "  {:<20} sqlite={:<6} postgres_было={:<6} {}"
        for spec in TABLES:
            table = spec["name"]
            total, before, added = await migrate_table(sconn, pconn, spec, dry_run)
            tail = "" if dry_run else f"добавлено={added}"
            print(rows_fmt.format(table, total, before, tail))

        if not dry_run:
            print("\nГотово.")
    finally:
        await pconn.close()
        sconn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqlite_path", nargs="?", default="data/bot.sqlite3",
                        help="путь к .sqlite3 (по умолчанию data/bot.sqlite3)")
    parser.add_argument("--database-url", default=None,
                        help="целевой Postgres DSN (по умолчанию — DATABASE_URL из .env)")
    parser.add_argument("--dry-run", action="store_true",
                        help="только посчитать строки, ничего не писать")
    args = parser.parse_args()

    path = Path(args.sqlite_path)
    if not path.is_absolute():
        path = ROOT / path
    database_url = args.database_url or settings.database_url

    asyncio.run(run(path, database_url, args.dry_run))


if __name__ == "__main__":
    main()
