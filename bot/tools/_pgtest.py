"""Готовит отдельную базу primeteens_test для tools/test_*.py и smoke.py —
чтобы прогоны не трогали ни боевую БД primeteens, ни (раньше) файлы SQLite.

Схему тестовой базе даёт не бот (он больше не создаёт и не мигрирует схему,
см. app/db.py:init) — тот же SQL, что Prisma накатывает на primeteens,
читаем напрямую из prisma/migrations/*/migration.sql. node/prisma CLI не
нужен.

Использование в начале tools/test_*.py, ДО `from app import db` /
`from app.config import settings` (Settings читает DATABASE_URL из
переменной окружения один раз, при импорте):

    import asyncio, os
    from tools._pgtest import TEST_DATABASE_URL, prepare
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

    from app import db  # noqa: E402

    async def main():
        await prepare()   # создаёт БД (если нет), схему (если нет), чистит таблицы
        await db.init()
        ...
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

_BOT_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BOT_ROOT.parent
MIGRATIONS_DIR = _REPO_ROOT / "prisma" / "migrations"

# bot/.env хранит боевой DATABASE_URL (та же primeteens, что и веб-платформа)
# — отсюда же берём хост/пользователя/пароль для тестовой базы, подменяя
# только имя БД. Файл не печатаем и не логируем целиком нигде ниже.
load_dotenv(_BOT_ROOT / ".env")

TEST_DB_NAME = "primeteens_test"


def _swap_db(url: str, name: str) -> str:
    """postgresql://user:pass@host:port/dbname?query -> .../name?query.
    asyncpg не понимает query-параметр ?schema= (это Prisma-специфика) —
    заодно срезаем всё после '?', он тестовой базе не нужен."""
    without_query = url.split("?", 1)[0]
    return re.sub(r"/[^/]*$", f"/{name}", without_query)


_PROD_URL = os.environ.get("DATABASE_URL", "")
TEST_DATABASE_URL = _swap_db(_PROD_URL, TEST_DB_NAME)
_MAINTENANCE_URL = _swap_db(_PROD_URL, "postgres")


async def _ensure_database() -> None:
    if not _PROD_URL:
        raise RuntimeError(
            "DATABASE_URL не задан (ни в окружении, ни в bot/.env) — "
            "нечего использовать как основу для primeteens_test."
        )
    conn = await asyncpg.connect(dsn=_MAINTENANCE_URL, server_settings={"client_encoding": "utf8"})
    try:
        row = await conn.fetchrow(
            "SELECT pg_encoding_to_char(encoding) AS enc FROM pg_database WHERE datname = $1",
            TEST_DB_NAME,
        )
        # embedded-postgres на этой машине поднялся с encoding=WIN1251 (кластер
        # унаследовал его от локали ОС при initdb — то же самое у боевой
        # primeteens, но это не наша забота: chinim только свою тестовую
        # базу). WIN1251 отлично хранит кириллицу, но роняет запись на любом
        # символе вне BMP (эмодзи в тестовых фикстурах, tools/smoke.py) —
        # тестовой базе явно нужен UTF8. LC_COLLATE/LC_CTYPE 'C' — потому что
        # шаблон template0 обычно тоже не в UTF8-локали, а 'C' работает с
        # любой кодировкой.
        if row is None:
            await conn.execute(
                f'CREATE DATABASE "{TEST_DB_NAME}" TEMPLATE template0 '
                f"ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C'"
            )
        elif row["enc"] != "UTF8":
            # одноразовая тестовая база — можно спокойно пересоздать
            await conn.execute(f'DROP DATABASE "{TEST_DB_NAME}"')
            await conn.execute(
                f'CREATE DATABASE "{TEST_DB_NAME}" TEMPLATE template0 '
                f"ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C'"
            )
    finally:
        await conn.close()


async def _ensure_schema(conn: asyncpg.Connection) -> None:
    has_groups = await conn.fetchval(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = 'groups'"
    )
    if has_groups:
        return
    migrations = sorted(MIGRATIONS_DIR.glob("*/migration.sql"))
    if not migrations:
        raise RuntimeError(f"Не нашёл ни одной миграции в {MIGRATIONS_DIR}")
    for migration in migrations:
        sql = migration.read_text(encoding="utf-8")
        await conn.execute(sql)  # без параметров -> simple query protocol, много стейтментов ок


async def _truncate_all(conn: asyncpg.Connection) -> None:
    rows = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    )
    tables = [r["tablename"] for r in rows if r["tablename"] != "_prisma_migrations"]
    if not tables:
        return
    names = ", ".join(f'"{t}"' for t in tables)
    await conn.execute(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE")


async def prepare() -> None:
    """Гарантирует, что primeteens_test существует, со схемой Prisma и
    пустыми таблицами. Звать ДО db.init() в каждом tools/test_*.py и в
    tools/smoke.py — каждый прогон стартует с чистого листа."""
    await _ensure_database()
    conn = await asyncpg.connect(dsn=TEST_DATABASE_URL, server_settings={"client_encoding": "utf8"})
    try:
        await _ensure_schema(conn)
        await _truncate_all(conn)
    finally:
        await conn.close()
