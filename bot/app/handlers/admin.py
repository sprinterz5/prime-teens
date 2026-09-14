"""Админские команды: группы, менторы, ученики, рассылка."""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import logging
import re
import secrets

import httpx
import openpyxl
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from app import db, keyboards as kb, roster_sheet
from app.config import COURSE, ROOT, settings
from app.handlers.registration import is_admin

log = logging.getLogger(__name__)
router = Router(name="admin")

TEMPLATE_PATH = ROOT / "seed" / "template.xlsx"


class AdminQuick(StatesGroup):
    """Мини-FSM для /set_start и /add_students без аргументов: выбрал группу
    кнопкой — бот сам спрашивает недостающее текстом. С аргументами команды
    работают как раньше, в один шаг, эти состояния вообще не задействуются."""
    set_start_date = State()
    add_students_text = State()


WEEKDAYS_RU = ["понедельник", "вторник", "среду", "четверг",
               "пятницу", "субботу", "воскресенье"]


def _parse_shift(raw: str) -> tuple[str | None, str | None, str]:
    """Третий параметр /add_group: утро/morning/10:00 -> смена morning,
    вечер/evening/18:00 -> смена evening, любое другое время — ручной
    override lesson_time (переопределяет смену). Возвращает
    (shift, lesson_time, примечание для ответа)."""
    v = raw.strip().lower()
    if v in {"утро", "morning", COURSE["shifts"]["morning"]["start"]}:
        return "morning", None, ""
    if v in {"вечер", "evening", COURSE["shifts"]["evening"]["start"]}:
        return "evening", None, ""
    return None, raw.strip(), (
        f"\n\n⏰ «{raw.strip()}» — не совпадает со сменами ({COURSE['shifts']['morning']['start']} "
        f"/ {COURSE['shifts']['evening']['start']}), сохранил как ручное время занятия "
        "(переопределяет смену на все дни)."
    )


def _format_label(g) -> str:
    fmt = g["format"] if "format" in g.keys() else None
    if fmt == "online":
        return " · онлайн"
    if fmt == "offline":
        return " · оффлайн"
    return ""


def _shift_label(g) -> str:
    if g["lesson_time"]:
        return f"ручное время {g['lesson_time']}" + _format_label(g)
    shift = COURSE["shifts"].get(g["shift"] or "evening", {})
    return f"{shift.get('label', g['shift'])} ({shift.get('start', '?')})" + _format_label(g)


def _monday_warning(date_iso: str) -> str:
    """Расписание считается смещениями от дня 1. Если старт не в понедельник,
    дни курса разъедутся с ожидаемыми пн/ср/пт/сб — предупреждаем, но не запрещаем."""
    wd = dt.date.fromisoformat(date_iso).weekday()
    if wd == 0:
        return ""
    return (f"\n\n⚠️ {date_iso} — это {WEEKDAYS_RU[wd]}, а не понедельник. "
            "Расписание всё равно построится (день 1, +2, +4, +5, +7…), "
            "но дни недели съедут. Если это не задумано — /set_start.")


async def _guard(message: Message) -> bool:
    if await is_admin(message.from_user.id):
        return True
    await message.answer("Команда только для администратора.")
    return False


@router.message(F.text == "⚙️ Админка")
@router.message(Command("admin"))
async def admin_help(message: Message) -> None:
    if not await _guard(message):
        return
    await message.answer(
        "<b>Админка</b>\n\n"
        "<code>/template</code>\n"
        "   пришлёт шаблон .xlsx (один лист, блоки групп друг под другом) — "
        "заполни ниже строки «Настоящие группы отсюда:» и пришли боту тем же "
        "файлом, дальше всё подтянется само\n\n"
        "<code>/sync_sheet</code>\n"
        "   забрать данные из Google-таблицы прямо сейчас (бот сам ходит по "
        "ссылке из SHEETS_SYNC_URL) — плюс то же самое раз в ночь автоматически, "
        "если ссылка настроена. Установка — integrations/README.md\n\n"
        "<code>/whoami</code> — твой Telegram ID (для ADMIN_IDS в .env)\n\n"
        "<code>/add_mentor +77011234567 Азиз Ким | Группа A</code>\n"
        "   вносит номер в белый список вручную; ментор потом жмёт /start\n\n"
        "<code>/invite</code>\n"
        "   меню ссылок: ментору (одноразовый пропуск в бота — группу возьмёт "
        "из ростера по своему номеру), ученикам (персональные одноразовые, "
        "каждому свой) или админу (одноразовая)\n\n"
        "<code>/groups</code> — активные группы, менторы, ученики "
        "(<code>/groups all</code> — вместе с завершёнными)\n"
        "<code>/students</code> — все ученики активных групп по группам\n"
        "<code>/today</code> — что сегодня по каждой активной группе\n"
        "<code>/overview</code> — сводка по курсу: группы, ученики, менторы, заполненность\n"
        "<code>/stats</code> — заполненность чек-листов\n"
        "<code>/broadcast текст</code> — всем менторам (не админам-организаторам)\n"
        "<code>/make_admin +77011234567</code> — выдать права администратора\n"
        "<code>/make_mentor +77011234567</code> — выдать роль ментора\n\n"
        "Ручной режим (на случай ошибки в экселе) — <code>/admin_manual</code>."
    )


@router.message(Command("admin_manual"))
async def admin_manual(message: Message) -> None:
    """Аварийный путь: заведение группы/учеников руками, если в Excel ошибка
    и разбираться с ней некогда. Основной путь — /template + присланный .xlsx."""
    if not await _guard(message):
        return
    await message.answer(
        "<b>Ручной режим</b> — аварийный путь, если в экселе что-то не так. "
        "Основной путь — /template, заполнить и прислать боту .xlsx.\n\n"
        "<code>/add_group Название | 2026-08-03 | вечер</code>\n"
        "   создать/обновить группу; дата — понедельник первой недели; смена — "
        "<code>утро</code> (10:00) или <code>вечер</code> (18:00); можно указать "
        "и произвольное время — оно сохранится как ручной override\n\n"
        "<code>/set_start Название | 2026-08-03</code> (или без аргументов — группа кнопкой)\n\n"
        "<code>/add_students Группа A</code> (или без аргументов — группа кнопкой)\n"
        "<code>Сейткали Алия</code>\n"
        "<code>Ли Данияр | 9 класс, НИШ</code>\n"
        "   каждый ученик с новой строки, класс — после |\n\n"
        "Ещё можно прислать CSV-файл (группа должна уже существовать в базе —\n"
        "своего листа «Группы» у CSV нет):\n"
        "  <code>mentors.csv</code>: phone,full_name,group,is_admin\n"
        "  <code>students.csv</code>: group,full_name,class_school,team"
    )


@router.message(Command("template"))
async def send_template(message: Message) -> None:
    if not await _guard(message):
        return
    if not TEMPLATE_PATH.exists():
        await message.answer(
            "Шаблон не найден на диске. Сгенерируй его: "
            "<code>.venv\\Scripts\\python.exe -m tools.make_template</code>"
        )
        return
    await message.answer_document(
        FSInputFile(TEMPLATE_PATH),
        caption=(
            "Шаблон для импорта. Один лист, блоки групп друг под другом "
            "(название, смена, дата старта, формат — в строке над шапкой "
            "«Ментор | Номер телефона | # | Ученик | Контакты | Школа | Класс»). "
            "Заполняй ТОЛЬКО ниже строки «Настоящие группы отсюда:» — то, что "
            "выше (Шаблон/Пример), не импортируется. Пришли этот же файл боту "
            "(.xlsx) — повторная присылка не плодит дублей, только добавляет "
            "и обновляет."
        ),
    )


@router.message(Command("add_group"))
async def add_group(message: Message, command: CommandObject) -> None:
    if not await _guard(message):
        return
    if not command.args:
        await message.answer("Формат: /add_group Название | 2026-08-03 | вечер")
        return
    parts = [p.strip() for p in command.args.split("|")]
    name = parts[0]
    start = parts[1] if len(parts) > 1 and parts[1] else None
    if start:
        try:
            dt.date.fromisoformat(start)
        except ValueError:
            await message.answer("Дата должна быть в формате ГГГГ-ММ-ДД.")
            return

    shift_, time_, override_note = (None, None, "")
    if len(parts) > 2 and parts[2]:
        shift_, time_, override_note = _parse_shift(parts[2])

    gid = await db.upsert_group(name, start, time_, shift_)
    await message.answer(
        f"Группа <b>{name}</b> сохранена (id {gid})."
        + (_monday_warning(start) if start else "")
        + override_note
    )


@router.message(Command("set_start"))
async def set_start(message: Message, command: CommandObject) -> None:
    if not await _guard(message):
        return
    args = (command.args or "").strip()
    if not args:
        groups = await db.groups()
        if not groups:
            await message.answer("Активных групп пока нет. Сначала /template или /add_group.")
            return
        await message.answer("Дата старта — для какой группы?",
                             reply_markup=kb.pick_group(groups, "adm:set_start"))
        return
    try:
        name, date = [p.strip() for p in args.split("|")]
        dt.date.fromisoformat(date)
    except Exception:
        await message.answer("Формат: /set_start Название | 2026-08-03")
        return
    await db.upsert_group(name, date)
    await message.answer(
        f"Старт группы <b>{name}</b>: {date}. Расписание пересчитано."
        + _monday_warning(date)
    )


@router.callback_query(F.data.startswith("adm:set_start:"))
async def set_start_pick_group(call: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(call.from_user.id):
        await call.answer("Только для администратора", show_alert=True)
        return
    g = await db.group(int(call.data.split(":")[2]))
    await state.update_data(quick_group_id=g["id"], quick_group_name=g["name"])
    await state.set_state(AdminQuick.set_start_date)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer()
    await call.message.answer(f"Группа <b>{g['name']}</b>. Дата старта — ГГГГ-ММ-ДД?")


@router.message(AdminQuick.set_start_date, F.text)
async def set_start_pick_date(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    if raw.startswith("/"):
        await state.clear()
        await message.answer("Отменил. Быстрый путь: /set_start Название | Дата.")
        return
    try:
        dt.date.fromisoformat(raw)
    except ValueError:
        await message.answer("Формат: ГГГГ-ММ-ДД, например 2026-08-03.")
        return
    data = await state.get_data()
    name = data["quick_group_name"]
    await db.upsert_group(name, raw)
    await state.clear()
    await message.answer(
        f"Старт группы <b>{name}</b>: {raw}. Расписание пересчитано."
        + _monday_warning(raw)
    )


@router.message(Command("add_mentor"))
async def add_mentor(message: Message, command: CommandObject) -> None:
    if not await _guard(message):
        return
    raw = command.args or ""
    if "|" not in raw:
        await message.answer("Формат: /add_mentor +77011234567 Имя Фамилия | Группа")
        return
    left, group_name = [p.strip() for p in raw.split("|", 1)]
    bits = left.split()
    if not bits:
        await message.answer("Не вижу номер телефона.")
        return
    phone = db.norm_phone(bits[0])
    full_name = " ".join(bits[1:]) or "Ментор"
    if len(phone) < 10:
        await message.answer("Номер выглядит странно. Нужен формат +77011234567.")
        return

    g = await db.q1("SELECT * FROM groups WHERE name = ?", group_name)
    if not g:
        await message.answer(f"Группы «{group_name}» нет. Сначала /add_group.")
        return
    await db.add_to_roster(phone, full_name, g["id"])

    # если ментор уже зарегистрирован — привязываем группу сразу
    m = await db.q1("SELECT * FROM mentors WHERE phone = ?", phone)
    if m:
        await db.link_mentor_group(m["id"], g["id"])
    await message.answer(
        f"{full_name} (+{phone}) → группа <b>{group_name}</b>.\n"
        "Пусть напишет боту /start и поделится номером."
    )


@router.message(Command("invite"))
async def invite_start(message: Message) -> None:
    if not await _guard(message):
        return
    await message.answer("Какую ссылку сделать?", reply_markup=kb.invite_menu())


async def _placeholder_group_id() -> int | None:
    """Ссылки роли 'mentor' и 'admin' в invites несут group_id только чтобы
    удовлетворить NOT NULL/FK — смысла у значения нет (см. комментарий в
    db.py про приглашения). Тут просто берём любую существующую группу,
    активную или нет — для FK это не важно. None, если групп нет вовсе."""
    groups = await db.groups(active_only=False)
    return groups[0]["id"] if groups else None


@router.callback_query(F.data == "inv:menu:mentor")
async def invite_menu_mentor(call: CallbackQuery, bot: Bot) -> None:
    if not await is_admin(call.from_user.id):
        await call.answer("Только для администратора", show_alert=True)
        return
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer()

    gid = await _placeholder_group_id()
    if gid is None:
        await call.message.answer(
            "Групп пока нет. Сначала /template (импорт Excel) или /add_group."
        )
        return

    token = secrets.token_urlsafe(8)
    # Менторская ссылка теперь одноразовая и БЕЗ группы: group_id тут ничего
    # не значит (см. _placeholder_group_id выше и комментарий в db.py).
    # Группу ментор получит по своему номеру телефона из roster.
    await db.create_invite(token, gid, created_by=call.from_user.id, role="mentor")
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=inv_{token}"
    await call.message.answer(
        f"Ссылка для ментора:\n<code>{link}</code>\n\n"
        "Одноразовая — просто пропуск в бота, без привязки к группе. Кто "
        "перейдёт и поделится номером — получит группу по своему номеру из "
        "ростера (загружен Excel-импортом или /add_mentor). Нет в ростере — "
        "бот попросит его подождать, пока админ добавит номер.",
        reply_markup=kb.invite_revoke(token),
    )


@router.callback_query(F.data == "inv:menu:students")
async def invite_menu_students(call: CallbackQuery) -> None:
    if not await is_admin(call.from_user.id):
        await call.answer("Только для администратора", show_alert=True)
        return
    groups = await db.groups()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer()
    if not groups:
        await call.message.answer("Активных групп пока нет. Сначала /template или /add_group.")
        return
    await call.message.answer("Ссылки для учеников — какой группы?",
                              reply_markup=kb.pick_group(groups, "inv:sgroup"))


def _chunk_lines(lines: list[str], limit: int = 3500) -> list[str]:
    """Режем список строк на сообщения под лимит Telegram (~4096 символов на
    сообщение) — с запасом под заголовок, который добавляется к первому куску."""
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for line in lines:
        if cur and cur_len + len(line) + 1 > limit:
            chunks.append("\n".join(cur))
            cur, cur_len = [], 0
        cur.append(line)
        cur_len += len(line) + 1
    if cur:
        chunks.append("\n".join(cur))
    return chunks


@router.callback_query(F.data.startswith("inv:sgroup:"))
async def invite_students_links(call: CallbackQuery) -> None:
    if not await is_admin(call.from_user.id):
        await call.answer("Только для администратора", show_alert=True)
        return
    g = await db.group(int(call.data.split(":")[2]))
    students = await db.students(g["id"])
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer()
    if not students:
        await call.message.answer(f"В группе «{g['name']}» пока нет учеников.")
        return

    # Повторный вызов не плодит дубли: у кого уже есть живая неиспользованная
    # ссылка — переиспользуем её токен, а не создаём новый.
    kids_bot = settings.kids_bot_username
    lines = []
    for st in students:
        existing = await db.active_student_invite(st["id"])
        token = existing["token"] if existing else secrets.token_urlsafe(8)
        if not existing:
            await db.create_invite(token, g["id"], created_by=call.from_user.id,
                                   role="student", student_id=st["id"])
        name = st["short_name"] or st["full_name"]
        if kids_bot:
            lines.append(f"{name} — https://t.me/{kids_bot}?start=inv_{token}")
        else:
            lines.append(f"{name} — <code>{token}</code>")

    if kids_bot:
        header = f"Ссылки для учеников группы <b>{g['name']}</b> (каждая одноразовая):\n\n"
    else:
        header = (
            "⚠️ Детский бот ещё не настроен — впиши KIDS_BOT_USERNAME в .env.\n"
            f"Токены для группы <b>{g['name']}</b> всё равно создал, вот они "
            "(ссылки соберутся сами, как только имя бота появится в .env):\n\n"
        )
    for i, chunk in enumerate(_chunk_lines(lines)):
        await call.message.answer((header if i == 0 else "") + chunk)


@router.callback_query(F.data == "inv:menu:admin")
async def invite_admin_link(call: CallbackQuery, bot: Bot) -> None:
    if not await is_admin(call.from_user.id):
        await call.answer("Только для администратора", show_alert=True)
        return
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer()

    gid = await _placeholder_group_id()
    if gid is None:
        await call.message.answer(
            "Сначала создай хотя бы одну группу (/template или /add_group) — "
            "без этого ссылку не создать."
        )
        return

    token = secrets.token_urlsafe(8)
    # group_id у admin-ссылки не значит ничего смыслового (в invites он NOT
    # NULL) — берём любую попавшуюся группу просто чтобы удовлетворить FK.
    await db.create_invite(token, gid, created_by=call.from_user.id, role="admin")
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=inv_{token}"
    await call.message.answer(
        f"Ссылка для администратора:\n<code>{link}</code>\n\n"
        "Одноразовая — сработает один раз, дальше отклонится. Даёт права "
        "администратора, но НЕ делает ментором ни одной группы.",
        reply_markup=kb.invite_revoke(token),
    )


@router.callback_query(F.data.startswith("inv:revoke:"))
async def invite_revoke_cb(call: CallbackQuery) -> None:
    if not await is_admin(call.from_user.id):
        await call.answer("Только для администратора", show_alert=True)
        return
    token = call.data.split(":", 2)[2]
    ok = await db.revoke_invite(token)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer("Отозвано" if ok else "Уже недействительна")
    await call.message.answer("🚫 Ссылка отозвана, больше не работает."
                              if ok else "Эта ссылка уже была отозвана раньше.")


async def _add_students_lines(g, lines: list[str]) -> tuple[int, int]:
    added = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        await db.add_student(g["id"], parts[0],
                             parts[1] if len(parts) > 1 else None,
                             parts[2] if len(parts) > 2 else None)
        added += 1
    total = len(await db.students(g["id"]))
    return added, total


@router.message(Command("add_students"))
async def add_students(message: Message, command: CommandObject) -> None:
    if not await _guard(message):
        return
    header = (command.args or "").strip()
    if not header:
        groups = await db.groups()
        if not groups:
            await message.answer("Активных групп пока нет. Сначала /template или /add_group.")
            return
        await message.answer("Ученики — для какой группы?",
                             reply_markup=kb.pick_group(groups, "adm:add_students"))
        return
    group_name = header.split("\n")[0].strip()
    g = await db.q1("SELECT * FROM groups WHERE name = ?", group_name)
    if not g:
        await message.answer(f"Группы «{group_name}» нет. Сначала /add_group.")
        return

    lines = (message.text or "").split("\n")[1:]
    added, total = await _add_students_lines(g, lines)
    await message.answer(f"Добавлено {added}. Всего в группе <b>{group_name}</b>: {total}.")


@router.callback_query(F.data.startswith("adm:add_students:"))
async def add_students_pick_group(call: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(call.from_user.id):
        await call.answer("Только для администратора", show_alert=True)
        return
    g = await db.group(int(call.data.split(":")[2]))
    await state.update_data(quick_group_id=g["id"], quick_group_name=g["name"])
    await state.set_state(AdminQuick.add_students_text)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer()
    await call.message.answer(
        f"Группа <b>{g['name']}</b>. Пришли учеников одним сообщением, "
        "каждый с новой строки:\n<code>Имя Фамилия | класс</code>"
    )


@router.message(AdminQuick.add_students_text, F.text)
async def add_students_pick_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if text.startswith("/"):
        await state.clear()
        await message.answer("Отменил. Быстрый путь: /add_students Группа A.")
        return
    data = await state.get_data()
    g = await db.group(data["quick_group_id"])
    added, total = await _add_students_lines(g, text.split("\n"))
    await state.clear()
    await message.answer(f"Добавлено {added}. Всего в группе <b>{g['name']}</b>: {total}.")


async def _group_end(g) -> dt.datetime | None:
    if not g["start_date"]:
        return None
    window = await db.group_lesson_window(g["id"], db.LAST_DAY_INDEX)
    return window[1] if window else None


@router.message(Command("groups"))
async def list_groups(message: Message, command: CommandObject) -> None:
    if not await _guard(message):
        return
    show_all = (command.args or "").strip().lower() == "all"
    groups = await db.groups(active_only=not show_all)
    if not groups:
        await message.answer("Групп пока нет." if show_all else
                             "Активных групп пока нет (/groups all — показать все).")
        return
    out = []
    for g in groups:
        mentors = await db.group_mentors(g["id"])
        students = await db.students(g["id"])
        tag = ""
        if show_all:
            end = await _group_end(g)
            finished = bool(end and end < dt.datetime.now(settings.tz))
            tag = (" · завершена " + end.strftime("%d.%m.%Y")) if finished else " · активна"
        out.append(
            f"<b>{g['name']}</b>{tag} · старт {g['start_date'] or '—'} · {_shift_label(g)}\n"
            f"менторы: {', '.join(m['full_name'] for m in mentors) or '—'}\n"
            f"учеников: {len(students)}\n"          # пустая строка — отступ между группами
        )
    header = "Все группы (в т.ч. завершённые):\n\n" if show_all else ""
    for i, chunk in enumerate(_chunk_lines(out)):
        await message.answer((header if i == 0 else "") + chunk)


@router.message(Command("stats"))
async def stats(message: Message) -> None:
    if not await _guard(message):
        return
    rows = await db.q(
        """SELECT g.name, s.day_index, s.kind, s.status, COUNT(a.id) AS answers
           FROM sessions s
           JOIN groups g ON g.id = s.group_id
           LEFT JOIN answers a ON a.session_id = s.id
           GROUP BY s.id ORDER BY g.name, s.kind, s.day_index"""
    )
    if not rows:
        await message.answer("Пока ни одного заполненного чек-листа.")
        return
    lines = [
        f"{r['name']} · {'финал' if r['kind'] == 'final' else 'день ' + str(r['day_index'])} · "
        f"{'✅' if r['status'] == 'done' else '⏳'} {r['answers']} ответов"
        for r in rows
    ]
    await message.answer("\n".join(lines))


def _day_kind(day: dict) -> str:
    return "hackathon" if day.get("hackathon") else "lesson"


@router.message(Command("today"))
async def today_cmd(message: Message) -> None:
    """Что сегодня: по каждой активной группе — время занятия и день курса;
    если занятие уже кончилось — кто отсутствовал (ключ absent_mark в answers,
    см. checklist.py: при мультивыборе «Кого не было» на каждого отмеченного
    сохраняется отдельная запись question_key = 'absent_mark')."""
    if not await _guard(message):
        return
    groups = await db.groups()
    now = dt.datetime.now(settings.tz)
    lines = []
    for g in groups:
        if not g["start_date"]:
            continue
        today = None
        window = None
        for d in COURSE["days"]:
            w = await db.group_lesson_window(g["id"], d["index"])
            if w and w[0].date() == now.date():
                today, window = d, w
                break
        if not today:
            continue
        start, end = window
        block = [
            f"<b>{g['name']}</b> · день {today['index']} — {today['title']} · "
            f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}"
        ]
        if now < start:
            block.append("  ещё не началось")
        elif now < end:
            block.append("  идёт сейчас")
        else:
            kind = _day_kind(today)
            done = await db.session_done(g["id"], today["index"], kind)
            if not done:
                block.append("  опрос ещё не заполнен")
            elif kind == "hackathon":
                # у опроса хакатона нет вопроса «кого не было» (см. course.yaml:
                # post_lesson_checklist) — про отсутствующих тут просто нечего сказать
                block.append("  опрос по хакатону заполнен")
            else:
                absent_rows = await db.q(
                    "SELECT student_id FROM answers WHERE group_id = ? AND day_index = ? "
                    "AND question_key = 'absent_mark'",
                    g["id"], today["index"],
                )
                if not absent_rows:
                    block.append("  отсутствующих нет")
                else:
                    names = []
                    for r in absent_rows:
                        st = await db.student(r["student_id"])
                        if st:
                            names.append(st["short_name"] or st["full_name"])
                    block.append("  отсутствовали: " + ", ".join(names))
        lines.append("\n".join(block))

    if not lines:
        await message.answer("Сегодня ни у одной активной группы нет занятия.")
        return
    for i, chunk in enumerate(_chunk_lines(lines)):
        await message.answer(("<b>Сегодня</b>\n\n" if i == 0 else "") + chunk)


@router.message(Command("students"))
async def students_cmd(message: Message) -> None:
    """Все ученики активных групп, по группам, с общим счётчиком."""
    if not await _guard(message):
        return
    groups = await db.groups()
    if not groups:
        await message.answer("Активных групп нет.")
        return
    total = 0
    lines = []
    for g in groups:
        sts = await db.students(g["id"])
        total += len(sts)
        body = "\n".join(f"  {i}. {s['full_name']}"
                         f"{' · ' + s['team'] if s['team'] else ''}"
                         for i, s in enumerate(sts, 1)) or "  (пусто)"
        lines.append(f"<b>{g['name']}</b> ({len(sts)}):\n{body}\n")
    header = f"<b>Ученики активных групп — всего {total}</b>\n\n"
    for i, chunk in enumerate(_chunk_lines(lines)):
        await message.answer((header if i == 0 else "") + chunk)


async def _expected_sessions(g, now: dt.datetime) -> int:
    """Сколько опросов уже должно было случиться к этому моменту: стартовый
    замер (как только у группы есть дата) + по одному на каждый день курса,
    чьё занятие уже началось. Грубая оценка «из скольких» для /overview."""
    if not g["start_date"]:
        return 0
    total = 1
    for d in COURSE["days"]:
        window = await db.group_lesson_window(g["id"], d["index"])
        if window and window[0] <= now:
            total += 1
    return total


@router.message(Command("overview"))
async def overview_cmd(message: Message) -> None:
    """Сводка по курсу: сколько активных групп/учеников/менторов, и по
    каждой группе — день курса сейчас, заполненность опросов, сколько
    учеников без единого эпизода (db.episode_counts)."""
    if not await _guard(message):
        return
    groups = await db.groups()
    if not groups:
        await message.answer("Активных групп нет.")
        return

    now = dt.datetime.now(settings.tz)
    total_students = 0
    mentor_ids: set[int] = set()
    lines = []
    for g in groups:
        sts = await db.students(g["id"])
        total_students += len(sts)
        for m in await db.group_mentors(g["id"]):
            mentor_ids.add(m["id"])

        cur_day = None
        if g["start_date"]:
            offset = (now.date() - g["start_date"]).days
            cur_day = next((d["index"] for d in COURSE["days"]
                            if int(d["offset_days"]) == offset), None)

        sessions = await db.q(
            "SELECT day_index, kind, status FROM sessions WHERE group_id = ?", g["id"])
        done_pairs = {(s["day_index"], s["kind"]) for s in sessions if s["status"] == "done"}
        expected = await _expected_sessions(g, now)

        counts = await db.episode_counts(g["id"])
        zero = sum(1 for s in sts if counts.get(s["id"], 0) == 0)

        lines.append(
            f"<b>{g['name']}</b>\n"
            f"  день курса сейчас: {cur_day if cur_day else '—'}\n"
            f"  опросов заполнено: {len(done_pairs)} из {expected}\n"
            f"  учеников без единого эпизода: {zero} из {len(sts)}\n"
        )

    header = (
        "<b>Сводка по курсу</b>\n"
        f"Активных групп: {len(groups)} · учеников: {total_students} · "
        f"менторов: {len(mentor_ids)}\n\n"
    )
    for i, chunk in enumerate(_chunk_lines(lines)):
        await message.answer((header if i == 0 else "") + chunk)


@router.message(Command("broadcast"))
async def broadcast(message: Message, command: CommandObject, bot: Bot) -> None:
    if not await _guard(message):
        return
    if not command.args:
        await message.answer("Формат: /broadcast текст сообщения")
        return
    # Только действующим менторам — чистый админ-организатор чек-листы не заполняет.
    mentors = await db.q("SELECT tg_user_id FROM mentors WHERE is_mentor")
    sent = 0
    for m in mentors:
        try:
            await bot.send_message(m["tg_user_id"], command.args)
            sent += 1
        except Exception:
            log.warning("Не доставлено: %s", m["tg_user_id"])
    await message.answer(f"Отправлено: {sent} из {len(mentors)}.")


@router.message(F.document)
async def handle_document(message: Message, bot: Bot) -> None:
    """Файл от админа: .xlsx — основной путь (шаблон из /template), .json —
    выгрузка из Google-таблицы через integrations/sheets_sync.gs, .csv —
    старый путь, оставлен рабочим на всякий случай."""
    if not await is_admin(message.from_user.id):
        return
    name = (message.document.file_name or "").lower()
    if name.endswith(".xlsx"):
        await _import_excel(message, bot)
    elif name.endswith(".json"):
        await _import_json_file(message, bot)
    elif name.endswith(".csv"):
        await _import_csv(message, bot)
    # другие расширения — не наш файл, молча игнорируем (как и раньше)


# ============================================================
# Импорт (.xlsx / .json / .csv) — общее ядро.
#
# Реальная таблица заказчика — ОДИН лист, сверху вниз идут блоки групп (имя/
# смена/дата/формат + менторы + ученики все вместе, см. app/roster_sheet.py
# за полным разбором формата). И .xlsx, и .json (выгрузка из Google-таблицы
# через integrations/sheets_sync.gs) сводятся к одному и тому же — сетке
# (список строк, строка — список значений ячеек) — и разбираются одним и тем
# же app.roster_sheet.parse_grid (см. _import_rows ниже). .csv — отдельный,
# старый однотабличный путь, оставлен рабочим на случай ошибки в Excel/Sheets
# (группа там должна уже существовать в базе — своего разбора блоков у CSV
# нет, см. _import_csv).
#
# Дальше все три формата сходятся в одном месте: три списка словарей —
# groups/mentors/students, дальше в _import_core. Вся построчная логика —
# валидация, upsert, сверка группы — живёт один раз там же. Форматы
# отличаются только тем, как они приводят свои строки к общему виду:
# list[dict] с ключами name/start_date/shift/format (группы), phone/
# full_name/group/role (менторы), group/full_name/class_school/team/phone
# (ученики) + служебный ключ "_row" — человекочитаемое место записи для
# сообщения об ошибке ("строка 5").
#
# Идемпотентно: группы/ученики — upsert по имени (db.upsert_group,
# db.add_student), менторы — upsert в roster по телефону (db.add_to_roster).
# Ничего не удаляется — повторная загрузка только добавляет/обновляет.
#
# Группа в «Менторах»/«Учениках» сверяется ТОЧНО со списком групп ЭТОГО ЖЕ
# импорта — если её там нет, строка не создаётся молча, а уходит в список
# проблем. Исключение — .csv: своего списка групп у него нет вообще, поэтому
# там группа ищется среди уже существующих в базе (extra_known_groups).
# ============================================================

def _text(v) -> str | None:
    """Ячейка -> строка. Числа (Excel любит хранить телефон/ФИО без кавычек
    как число) приводятся аккуратно, без хвоста «.0»."""
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    return s or None


def _parse_date_cell(v) -> str | None:
    """Ячейка с датой -> ISO-строка. Excel обычно отдаёт datetime/date сам,
    но подстрахуемся и на случай текстовой ячейки (ISO или ДД.ММ.ГГГГ)."""
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    s = str(v).strip()
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s).isoformat()
    except ValueError:
        pass
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_role_ru(raw: str | None) -> tuple[bool, bool]:
    """Роль в «Менторах»: «ментор» / «админ» / «ментор, админ» (пусто =
    ментор). Возвращает (is_mentor, is_admin)."""
    v = (raw or "").strip().lower()
    if not v:
        return True, False
    parts = {p.strip() for p in re.split(r"[,;/]", v) if p.strip()}
    is_admin = any("админ" in p for p in parts)
    is_mentor = any("ментор" in p for p in parts)
    if not is_admin and not is_mentor:
        # неопознанное значение — не теряем человека молча, считаем ментором
        is_mentor = True
    return is_mentor, is_admin


def _fields_blank(rec: dict, keys: tuple[str, ...]) -> bool:
    """Заменяет прежний _row_is_blank: та же проверка «все поля пустые»,
    но не завязана на конкретный excel-row/индексы колонок — просто набор
    ключей в уже-приведённом словаре записи (см. _import_core)."""
    return all(_text(rec.get(k)) is None for k in keys)


async def _import_core(
    groups_rows: list[dict],
    mentors_rows: list[dict],
    students_rows: list[dict],
    *,
    group_ctx: str = "лист Группы",
    mentor_ctx: str = "лист Менторы",
    student_ctx: str = "лист Ученики",
    group_missing_suffix: str = "нет на листе «Группы»",
    extra_known_groups: dict[str, int] | None = None,
) -> dict:
    """Общее ядро импорта — построчная логика, которая раньше жила прямо
    внутри import_workbook. Ничего не знает про Excel/JSON/CSV/сетку — этим
    занимаются функции выше по стеку (_import_rows + app.roster_sheet.parse_grid
    для .xlsx/.json, _import_csv для .csv), которые приводят свой формат к
    трём спискам словарей одного вида:

      groups:   {"name", "start_date", "shift", "format", "_row"}
      mentors:  {"phone", "full_name", "group", "role", "_row"}
      students: {"group", "full_name", "class_school", "team", "phone", "_row"}

    "format"/"phone" — необязательные ключи (online/offline у группы, номер
    ученика из колонки «Контакты»); источники, у которых их нет (CSV, ручной
    ввод), просто не кладут ключ — rec.get(...) вернёт None, ничего не сломается.

    "_row" — человекочитаемое место записи для сообщения об ошибке: «строка
    5» у листа/CSV, «элемент 2» (индекс с нуля) у JSON. group_ctx/mentor_ctx/
    student_ctx/group_missing_suffix — как называть источник и куда отсылать
    в сообщениях об ошибках; у .xlsx и .json это разные слова (лист/список),
    подставляются вызывающей стороной, сама построчная логика от них не
    зависит.

    Идемпотентно: группы/ученики — upsert по имени (db.upsert_group,
    db.add_student), менторы — upsert в roster по телефону (db.add_to_roster).
    Ничего не удаляется — повторный импорт только добавляет/обновляет.

    Группа у ментора/ученика сверяется ТОЧНО со списком групп ЭТОГО ЖЕ
    импорта (groups_rows) — если её там нет, строка не создаётся молча, а
    уходит в errors. extra_known_groups — лазейка для .csv, у которого своего
    списка групп вообще нет: туда передаются уже существующие в базе группы,
    чтобы ссылка на реально заведённую группу не считалась ошибкой."""
    errors: list[str] = []
    skipped_empty = 0
    groups_created = groups_updated = 0
    mentors_count = 0
    students_count = 0

    # ---------------------------------------------------------------- Группы
    group_ids: dict[str, int] = {}   # точное имя (как в этом же импорте) -> id
    for rec in groups_rows:
        row = rec["_row"]
        if _fields_blank(rec, ("name", "start_date", "shift")):
            continue
        name = _text(rec.get("name"))
        if not name:
            errors.append(f"{group_ctx}, {row}: пустое название")
            skipped_empty += 1
            continue
        name = name.strip()
        existing = await db.q1("SELECT id FROM groups WHERE name = ?", name)

        start_date = None
        start_raw = rec.get("start_date")
        if _text(start_raw) is not None:
            start_date = _parse_date_cell(start_raw)
            if start_date is None:
                errors.append(f"{group_ctx}, {row}: дата «{start_raw}» не распознана")

        shift_val = time_val = None
        shift_raw = _text(rec.get("shift"))
        if shift_raw:
            shift_val, time_val, _note = _parse_shift(shift_raw)

        fmt_val = _text(rec.get("format"))
        if fmt_val and fmt_val not in ("online", "offline"):
            # источник (roster_sheet) уже нормализует к online/offline — сюда
            # попадает только что-то нестандартное из ручного/CSV-пути
            errors.append(f"{group_ctx}, {row}: формат «{fmt_val}» не распознан (online/offline)")
            fmt_val = None

        gid = await db.upsert_group(name, start_date, time_val, shift_val, fmt_val)
        group_ids[name] = gid
        if existing:
            groups_updated += 1
        else:
            groups_created += 1

    known_groups = dict(extra_known_groups or {})
    known_groups.update(group_ids)  # список из этого же импорта важнее «внешних»

    # --------------------------------------------------------------- Менторы
    for rec in mentors_rows:
        row = rec["_row"]
        if _fields_blank(rec, ("phone", "full_name", "group", "role")):
            continue
        phone_raw = _text(rec.get("phone"))
        name = _text(rec.get("full_name"))
        if not phone_raw or not name:
            errors.append(f"{mentor_ctx}, {row}: не хватает телефона или ФИО")
            skipped_empty += 1
            continue
        phone = db.norm_phone(phone_raw)
        if len(phone) < 10:
            errors.append(f"{mentor_ctx}, {row}: телефон «{phone_raw}» не похож на номер")
            skipped_empty += 1
            continue

        group_raw = _text(rec.get("group"))
        gid = None
        if group_raw:
            gid = known_groups.get(group_raw.strip())
            if gid is None:
                errors.append(f"{mentor_ctx}, {row}: группы «{group_raw}» {group_missing_suffix}")
                continue

        role_raw = _text(rec.get("role"))
        is_mentor, is_admin = _parse_role_ru(role_raw)
        await db.add_to_roster(phone, name, gid, is_admin, is_mentor)
        mentors_count += 1

        # уже зарегистрированному ментору группа привязывается сразу
        m = await db.mentor_by_phone(phone)
        if m and gid:
            await db.link_mentor_group(m["id"], gid)

    # --------------------------------------------------------------- Ученики
    for rec in students_rows:
        row = rec["_row"]
        if _fields_blank(rec, ("group", "full_name", "class_school", "team")):
            continue
        group_raw = _text(rec.get("group"))
        name = _text(rec.get("full_name"))
        if not group_raw or not name:
            errors.append(f"{student_ctx}, {row}: не хватает группы или ФИО")
            skipped_empty += 1
            continue
        gid = known_groups.get(group_raw.strip())
        if gid is None:
            errors.append(f"{student_ctx}, {row}: группы «{group_raw}» {group_missing_suffix}")
            continue
        class_school = _text(rec.get("class_school"))
        team = _text(rec.get("team"))
        phone_raw = _text(rec.get("phone"))
        phone = db.norm_phone(phone_raw) if phone_raw else None
        await db.add_student(gid, name, class_school, team, phone or None)
        students_count += 1

    return {
        "groups_created": groups_created,
        "groups_updated": groups_updated,
        "mentors_count": mentors_count,
        "students_count": students_count,
        "skipped_empty": skipped_empty,
        "errors": errors,
    }


# ---------------------------------------------------- .xlsx / .json -> сетка -> roster_sheet

def _sheet_to_grid(ws) -> list[list]:
    return [[c.value for c in row] for row in ws.iter_rows()]


def _pick_sheet(wb):
    """Первый лист книги — если их несколько, берём тот, где реально больше
    заполненных строк (на случай, если кто-то оставил лишний пустой лист
    первым по счёту)."""
    def _nonblank_rows(ws) -> int:
        n = 0
        for row in ws.iter_rows():
            if any(c.value not in (None, "") for c in row):
                n += 1
        return n

    best = wb.worksheets[0]
    best_n = _nonblank_rows(best)
    for ws in wb.worksheets[1:]:
        n = _nonblank_rows(ws)
        if n > best_n:
            best, best_n = ws, n
    return best


async def _import_rows(rows: list[list]) -> dict:
    """Общий путь для .xlsx и .json — обе сводятся к сетке (список строк,
    строка — список значений ячеек), дальше app.roster_sheet.parse_grid
    разбирает блоки групп, а _import_core делает upsert/сверку/отчёт."""
    group_rows, mentor_rows, student_rows, problems = roster_sheet.parse_grid(rows)
    report = await _import_core(
        group_rows, mentor_rows, student_rows,
        group_ctx="таблица", mentor_ctx="таблица", student_ctx="таблица",
        group_missing_suffix="не нашлась среди блоков групп в этой же таблице "
                             "(ниже строки «Настоящие группы отсюда:»)",
    )
    report["errors"] = problems + report["errors"]
    return report


async def import_workbook(wb) -> dict:
    """Вся логика импорта поверх уже открытой openpyxl-книги — без Telegram,
    отдельно от _import_excel, чтобы можно было гонять из tools/test_excel.py
    без бота. Берёт лист сеткой (_sheet_to_grid) и отдаёт в общий _import_rows
    (там же живёт и import_json)."""
    ws = _pick_sheet(wb)
    return await _import_rows(_sheet_to_grid(ws))


# ---------------------------------------------------- .json: синхронизация с Google-таблицей

async def import_json(data: dict) -> dict:
    """Импорт из JSON, который шлёт integrations/sheets_sync.gs (Apps Script
    в самой Google-таблице — см. integrations/README.md за форматом и
    настройкой): {"source", "spreadsheet", "exported_at", "rows": [[...], ...]}
    — "rows" это СЫРАЯ сетка листа (getDataRange().getValues()), разбор
    полностью на стороне Python (roster_sheet), скрипт ничего не парсит.
    То же ядро, что у .xlsx — см. _import_rows."""
    pre_errors: list[str] = []
    raw_rows = data.get("rows")
    if raw_rows is None:
        pre_errors.append("не нашёл список «rows» в JSON")
        raw_rows = []
    elif not isinstance(raw_rows, list):
        pre_errors.append("«rows» в JSON должен быть списком строк (строка — список ячеек)")
        raw_rows = []
    rows = [r if isinstance(r, list) else [] for r in raw_rows]

    report = await _import_rows(rows)
    report["errors"] = pre_errors + report["errors"]
    report["source"] = data.get("source")
    report["spreadsheet"] = data.get("spreadsheet")
    report["sheet"] = data.get("sheet")
    report["exported_at"] = data.get("exported_at")
    return report


def _format_import_report(report: dict, title: str = "Импорт из Excel завершён.") -> list[str]:
    lines = [f"<b>{title}</b>"]
    if report.get("source"):
        meta = f"Источник: {report['source']}"
        if report.get("spreadsheet"):
            meta += f" · «{report['spreadsheet']}»"
        if report.get("sheet"):
            meta += f" · лист «{report['sheet']}»"
        if report.get("exported_at"):
            meta += f" · выгружено {report['exported_at']}"
        lines.append(meta)
    lines += [
        f"Группы: создано {report['groups_created']}, обновлено {report['groups_updated']}.",
        f"Менторы (в ростере): {report['mentors_count']}.",
        f"Ученики: {report['students_count']}.",
    ]
    if report["skipped_empty"]:
        lines.append(f"Пропущено пустых/неполных строк: {report['skipped_empty']}.")
    # Справка (разрешённые даты старта) — это подтверждение, а не ошибка.
    # Если валить её в «Проблемные строки», каждая успешная синхронизация
    # выглядит проблемной, и на предупреждения перестают смотреть.
    notes = [e for e in report["errors"] if str(e).startswith(roster_sheet.INFO_PREFIX)]
    errors = [e for e in report["errors"] if not str(e).startswith(roster_sheet.INFO_PREFIX)]
    if notes:
        lines.append("\n<b>Справочно:</b>")
        lines.extend("  " + str(n)[len(roster_sheet.INFO_PREFIX):] for n in notes)
    if errors:
        lines.append(f"\n⚠️ <b>Проблемные строки ({len(errors)}):</b>")
        lines.extend(f"  {e}" for e in errors)
    else:
        lines.append("\nПроблем не найдено.")
    return lines


async def _import_excel(message: Message, bot: Bot) -> None:
    doc = message.document
    buf = io.BytesIO()
    await bot.download(doc.file_id, destination=buf)
    buf.seek(0)
    try:
        wb = openpyxl.load_workbook(buf, data_only=True)
    except Exception as e:  # noqa: BLE001
        await message.answer(f"Не смог открыть файл: {e}")
        return

    report = await import_workbook(wb)
    for chunk in _chunk_lines(_format_import_report(report)):
        await message.answer(chunk)


async def _import_json_file(message: Message, bot: Bot) -> None:
    """Файл от Apps Script (см. integrations/sheets_sync.gs) — тот же импорт,
    что у .xlsx, но без Excel: JSON с тремя списками groups/mentors/students.
    Формат и настройка — integrations/README.md."""
    doc = message.document
    buf = io.BytesIO()
    await bot.download(doc.file_id, destination=buf)
    try:
        data = json.loads(buf.getvalue().decode("utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        await message.answer(f"Не смог разобрать JSON: {e}")
        return
    if not isinstance(data, dict):
        await message.answer("Ожидал JSON-объект с ключами groups/mentors/students.")
        return

    report = await import_json(data)
    title = "Синхронизация с Google-таблицей завершена." if report.get("source") \
        else "Импорт из JSON завершён."
    for chunk in _chunk_lines(_format_import_report(report, title=title)):
        await message.answer(chunk)


async def pull_sheet() -> dict:
    """Забирает данные из опубликованного Web App (integrations/sheets_sync.gs)
    по HTTP и прогоняет через тот же импорт, что .json-файл — см. import_json.

    Раньше было наоборот: таблица САМА слала боту документ через Bot API
    (sendDocument). Не сработало — с точки зрения Telegram сообщение шлёт
    бот, а не человек, и getUpdates такое эхо своих же исходящих не
    возвращает. Пул с этой стороны, наоборот, обычный HTTP GET — бот сам
    инициирует, ему ничего не должно «прилететь» само.

    Возвращает тот же формат отчёта, что _import_rows/import_json, плюс
    может содержать "_fatal" — тогда импорта не было вовсе (сеть/секрет/
    неверный ответ), это отдельно от report["errors"] (те — про отдельные
    строки листа, а не про сам факт синхронизации)."""
    if not settings.sheets_sync_url:
        return {"_fatal": "SHEETS_SYNC_URL не задан в .env — синхронизация не настроена."}

    try:
        # follow_redirects обязателен: /exec-ссылки Apps Script почти всегда
        # сперва отвечают 302 на script.googleusercontent.com, и уже ТАМ
        # реально лежит JSON от doGet. httpx редиректы по умолчанию не
        # проходит (в отличие от requests) — без этого параметра сюда всегда
        # прилетал бы код 302 вместо тела ответа. Проверено на живой ссылке.
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(settings.sheets_sync_url,
                                    params={"token": settings.sheets_sync_token})
    except Exception as e:  # noqa: BLE001
        return {"_fatal": f"не достучался до Google-таблицы: {e}"}

    if resp.status_code != 200:
        return {"_fatal": f"таблица ответила кодом {resp.status_code} (ждали 200)"}
    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        return {"_fatal": "ответ таблицы не похож на JSON — проверь ссылку и деплой Web App"}
    if not isinstance(data, dict):
        return {"_fatal": "ответ таблицы — не JSON-объект"}
    if not data.get("ok"):
        return {"_fatal": data.get("error") or "таблица вернула ok: false без пояснения"}

    return await import_json(data)


@router.message(Command("sync_sheet"))
async def sync_sheet_cmd(message: Message) -> None:
    if not await _guard(message):
        return
    note = await message.answer("Забираю данные из Google-таблицы…")
    report = await pull_sheet()
    if report.get("_fatal"):
        await note.edit_text(f"Не вышло: {report['_fatal']}")
        return
    await note.delete()
    for chunk in _chunk_lines(_format_import_report(
            report, title="Синхронизация с Google-таблицей завершена.")):
        await message.answer(chunk)


async def _import_csv(message: Message, bot: Bot) -> None:
    """mentors.csv: phone,full_name,group,is_admin | students.csv: group,full_name,class_school,team.

    Старый однотабличный путь — оставлен рабочим на всякий случай, основной
    путь теперь .xlsx или синхронизация из Google-таблицы (.json). Идёт через
    то же ядро _import_core, что .xlsx и .json — только своего списка групп у
    CSV нет вообще, поэтому группа ищется среди уже заведённых в базе
    (extra_known_groups), а не создаётся молча и не пропускается тихо, как
    раньше."""
    doc = message.document
    buf = io.BytesIO()
    await bot.download(doc.file_id, destination=buf)
    text = buf.getvalue().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    fields = {(f or "").strip().lower() for f in (reader.fieldnames or [])}
    known_groups = {r["name"]: r["id"] for r in await db.q("SELECT id, name FROM groups")}

    if {"phone", "full_name"} <= fields:
        mentor_rows = []
        for i, row in enumerate(reader):
            is_admin_flag = str(row.get("is_admin", "")).strip() in {"1", "true", "yes", "да"}
            # старый csv не различал is_mentor отдельно от is_admin — ментор
            # всегда True, админ-флаг просто добавляется поверх. Синтезируем
            # role-строку, чтобы _parse_role_ru внутри ядра дала тот же
            # результат, что и раньше.
            role = "ментор, админ" if is_admin_flag else "ментор"
            mentor_rows.append({
                "phone": row.get("phone"), "full_name": row.get("full_name") or "Ментор",
                "group": row.get("group"), "role": role, "_row": f"строка {i + 2}",
            })
        report = await _import_core(
            [], mentor_rows, [],
            mentor_ctx="CSV", group_missing_suffix="нет среди уже заведённых групп",
            extra_known_groups=known_groups,
        )
        title = "Импорт менторов из CSV завершён."
        for chunk in _chunk_lines(_format_import_report(report, title=title)):
            await message.answer(chunk)
    elif {"group", "full_name"} <= fields:
        student_rows = []
        for i, row in enumerate(reader):
            student_rows.append({
                "group": row.get("group"), "full_name": row.get("full_name"),
                "class_school": row.get("class_school"), "team": row.get("team"),
                "_row": f"строка {i + 2}",
            })
        report = await _import_core(
            [], [], student_rows,
            student_ctx="CSV", group_missing_suffix="нет среди уже заведённых групп",
            extra_known_groups=known_groups,
        )
        title = "Импорт учеников из CSV завершён."
        for chunk in _chunk_lines(_format_import_report(report, title=title)):
            await message.answer(chunk)
    else:
        await message.answer(
            "Не понял колонки. Нужны либо phone,full_name,group,is_admin, "
            "либо group,full_name,class_school,team."
        )
