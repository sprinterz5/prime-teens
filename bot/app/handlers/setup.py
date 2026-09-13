"""ОТКЛЮЧЕНО: мастер /setup закомментирован целиком.

Чем заменён: заведение группы/менторов/учеников теперь идёт Excel-импортом
(/template + присланный .xlsx — см. app/handlers/admin.py:_import_excel).
Он покрывает тот же сценарий (название, дата, смена, менторы, ученики) целиком
за один файл, поэтому пошаговый мастер больше не нужен на основном пути.

Код мастера не удалён — он ниже, целиком обёрнут в тройные кавычки как один
большой блок-комментарий, и поэтому не исполняется (router модуля не создаётся
и никуда не подключается).

Что раскомментировать, если Excel-путь вдруг не подойдёт:
  1. убрать тройные кавычки ниже — открывающую (сразу после этого докстринга)
     и закрывающую (последняя строка файла);
  2. в app/handlers/__init__.py раскомментировать `from app.handlers import setup`
     и `root.include_router(setup.router)`.

Дальше — исходный модуль без единой смысловой правки.
"""

r'''
"""Мастер /setup — одна проводка через название, дату, смену и учеников.

Зачем: до этого название группы вводилось строкой три раза подряд
(/add_group, /add_mentor, /add_students), и опечатка — особенно
неразличимая глазами (латинская A вместо кириллической А) — тихо
создавала вторую группу-дубль, потому что upsert_group ищет по имени.
Мастер решает это одним диалогом: имя вводится один раз, а перед
созданием группы её название сверяется с уже существующими (difflib).

Ничего не пишется в базу, пока админ не подтвердит итоговую карточку —
можно сколько угодно поправлять шаги назад через «Начать заново» или
выйти совсем через /stop, не оставив следа в БД.
"""
from __future__ import annotations

import datetime as dt
import difflib
import re
from typing import Any, Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app import db, keyboards as kb
from app.config import COURSE, settings
from app.handlers.admin import _monday_warning
from app.handlers.registration import WEEKDAYS, is_admin

router = Router(name="setup")

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
_SIMILARITY_THRESHOLD = 0.8


class SetupWizard(StatesGroup):
    name = State()
    confirm_similar = State()
    start_date = State()
    shift = State()
    shift_time = State()
    students = State()
    confirm = State()


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _find_similar(name: str, groups: list[Any]) -> tuple[Optional[Any], float]:
    best, best_ratio = None, 0.0
    for g in groups:
        ratio = _similarity(name, g["name"])
        if ratio > best_ratio:
            best, best_ratio = g, ratio
    return best, best_ratio


def _next_mondays(n: int = 3) -> list[dt.date]:
    """Ближайшие n понедельников, считая сегодняшний день, если он сам — понедельник."""
    today = dt.datetime.now(settings.tz).date()
    offset = (0 - today.weekday()) % 7
    first = today + dt.timedelta(days=offset)
    return [first + dt.timedelta(weeks=i) for i in range(n)]


def _shift_label(shift: str | None, lesson_time: str | None) -> str:
    if lesson_time:
        return f"ручное время {lesson_time}"
    s = COURSE["shifts"].get(shift or "evening", {})
    return f"{s.get('label', shift)} ({s.get('start', '?')})"


def _preview_schedule(start_date_iso: str, shift: str | None, lesson_time: str | None) -> str:
    """Расписание дня 1 без единой записи в БД — по тем же правилам, что
    db.group_lesson_window/_lesson_start_hm, но на «сыром» наборе полей."""
    day = db._day_by_index(1)
    if not day:
        return ""
    hh, mm = db._lesson_start_hm({"lesson_time": lesson_time, "shift": shift}, day)
    date = dt.date.fromisoformat(start_date_iso) + dt.timedelta(days=int(day["offset_days"]))
    start = dt.datetime(date.year, date.month, date.day, hh, mm, tzinfo=settings.tz)
    end = start + dt.timedelta(minutes=db._lesson_duration_minutes(day))
    lines = [
        f"День 1 — {WEEKDAYS[start.weekday()]} {start.strftime('%d.%m')}, "
        f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')} ({day.get('title', '')})"
    ]
    for t0, t1, block in db.day_block_times(day, start):
        lines.append("    " + db.fmt_block(t0, t1, block))
    return "\n".join(lines)


async def _guard(message: Message) -> bool:
    if await is_admin(message.from_user.id):
        return True
    await message.answer("Команда только для администратора.")
    return False


# ----------------------------------------------------------------- вход и выход

@router.message(Command("setup"))
async def setup_start(message: Message, state: FSMContext) -> None:
    if not await _guard(message):
        return
    await state.clear()
    await state.set_state(SetupWizard.name)
    await message.answer(
        "<b>Мастер настройки группы</b>\n\n"
        "Шаг 1/4. Название группы?\n\n"
        "Прервать в любой момент — /stop.",
    )


@router.message(Command("stop"), SetupWizard.name)
@router.message(Command("stop"), SetupWizard.confirm_similar)
@router.message(Command("stop"), SetupWizard.start_date)
@router.message(Command("stop"), SetupWizard.shift)
@router.message(Command("stop"), SetupWizard.shift_time)
@router.message(Command("stop"), SetupWizard.students)
@router.message(Command("stop"), SetupWizard.confirm)
async def stop_setup(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Мастер прерван, ничего не сохранилось. Начать заново — /setup.")


# ----------------------------------------------------------------- шаг 1: название

@router.message(SetupWizard.name, F.text)
async def got_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if name.startswith("/"):
        await message.answer("Мастер активен, жду название группы. Выйти — /stop.")
        return
    if not name:
        await message.answer("Название не может быть пустым.")
        return

    existing = await db.groups()
    best, ratio = _find_similar(name, existing)

    if best and best["name"].lower() == name.lower():
        # точное совпадение без учёта регистра — дублей тут не будет,
        # просто продолжаем с этой же группой
        await state.update_data(name=best["name"], existing_group_id=best["id"])
        await message.answer(f"Группа «{best['name']}» уже есть — продолжаем с ней.")
        await _ask_date(message, state)
        return

    if best and ratio > _SIMILARITY_THRESHOLD:
        await state.update_data(pending_name=name)
        await state.set_state(SetupWizard.confirm_similar)
        await message.answer(
            f"⚠️ Есть похожая группа: «<b>{best['name']}</b>» (совпадение {int(ratio * 100)}%).\n"
            "Частая причина — опечатка или похожая буква из другого алфавита "
            "(латинская вместо кириллической). Это она, или заводим новую?",
            reply_markup=kb.setup_similar(best["id"], best["name"]),
        )
        return

    await state.update_data(name=name, existing_group_id=None)
    await _ask_date(message, state)


@router.callback_query(F.data.startswith("su:same:"), SetupWizard.confirm_similar)
async def similar_use_existing(call: CallbackQuery, state: FSMContext) -> None:
    gid = int(call.data.split(":")[2])
    g = await db.group(gid)
    await state.update_data(name=g["name"], existing_group_id=gid)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer("Используем существующую")
    await _ask_date(call.message, state)


@router.callback_query(F.data == "su:new", SetupWizard.confirm_similar)
async def similar_create_new(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.update_data(name=data.get("pending_name"), existing_group_id=None)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer("Создаём новую")
    await _ask_date(call.message, state)


# ----------------------------------------------------------------- шаг 2: дата старта

async def _ask_date(message: Message, state: FSMContext) -> None:
    await state.set_state(SetupWizard.start_date)
    options = [(f"Пн {d.strftime('%d.%m')}", d.isoformat()) for d in _next_mondays(3)]
    await message.answer(
        "Шаг 2/4. Дата старта — день 1, понедельник первой недели курса.\n"
        "Кнопкой ниже или текстом ГГГГ-ММ-ДД.",
        reply_markup=kb.setup_mondays(options),
    )


async def _after_date(message: Message, state: FSMContext, date_iso: str) -> None:
    await state.update_data(start_date=date_iso)
    warn = _monday_warning(date_iso)
    await state.set_state(SetupWizard.shift)
    morning, evening = COURSE["shifts"]["morning"], COURSE["shifts"]["evening"]
    await message.answer(
        f"Дата: {date_iso}.{warn}\n\nШаг 3/4. Смена?",
        reply_markup=kb.setup_shift(
            f"🌅 {morning['label'].capitalize()} ({morning['start']})",
            f"🌆 {evening['label'].capitalize()} ({evening['start']})",
        ),
    )


@router.callback_query(F.data.startswith("su:date:"), SetupWizard.start_date)
async def date_button(call: CallbackQuery, state: FSMContext) -> None:
    date_iso = call.data.split(":", 2)[2]
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer()
    await _after_date(call.message, state, date_iso)


@router.message(SetupWizard.start_date, F.text)
async def date_text(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    if raw.startswith("/"):
        await message.answer("Мастер активен, жду дату. Выйти — /stop.")
        return
    try:
        dt.date.fromisoformat(raw)
    except ValueError:
        await message.answer("Формат: ГГГГ-ММ-ДД, например 2026-08-03. Или кнопкой выше.")
        return
    await _after_date(message, state, raw)


# ----------------------------------------------------------------- шаг 3: смена

@router.callback_query(F.data.in_({"su:shift:morning", "su:shift:evening"}), SetupWizard.shift)
async def shift_pick(call: CallbackQuery, state: FSMContext) -> None:
    shift = call.data.split(":")[2]
    await state.update_data(shift=shift, lesson_time=None)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer()
    await _ask_students(call.message, state)


@router.callback_query(F.data == "su:shift:custom", SetupWizard.shift)
async def shift_custom(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SetupWizard.shift_time)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer()
    await call.message.answer("Во сколько? Формат ЧЧ:ММ, например 19:30.")


@router.message(SetupWizard.shift_time, F.text)
async def shift_custom_text(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    if raw.startswith("/"):
        await message.answer("Мастер активен, жду время. Выйти — /stop.")
        return
    m = _TIME_RE.match(raw)
    if not m:
        await message.answer("Не понял время. Формат ЧЧ:ММ, например 19:30.")
        return
    time_str = f"{int(m.group(1)):02d}:{m.group(2)}"
    await state.update_data(shift=None, lesson_time=time_str)
    await _ask_students(message, state)


# ----------------------------------------------------------------- шаг 4: ученики

async def _ask_students(message: Message, state: FSMContext) -> None:
    await state.set_state(SetupWizard.students)
    await message.answer(
        "Шаг 4/4. Ученики — одним сообщением, каждый с новой строки:\n"
        "<code>Имя Фамилия | класс</code>\n\n"
        "Класс можно не указывать. Можно и вовсе добавить позже — кнопка ниже.",
        reply_markup=kb.setup_skip_students(),
    )


@router.callback_query(F.data == "su:skip_students", SetupWizard.students)
async def students_skip(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(students_raw=[])
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer()
    await _show_summary(call.message, state)


@router.message(SetupWizard.students, F.text)
async def students_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if text.startswith("/"):
        await message.answer("Мастер активен, жду список учеников. Выйти — /stop.")
        return
    parsed: list[tuple[str, str | None]] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        parsed.append((parts[0], parts[1] if len(parts) > 1 and parts[1] else None))
    if not parsed:
        await message.answer("Не разобрал ни одной строки. Формат: Имя Фамилия | класс.")
        return
    await state.update_data(students_raw=parsed)
    await _show_summary(message, state)


# ----------------------------------------------------------------- итоговая карточка

async def _show_summary(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(SetupWizard.confirm)

    name = data["name"]
    start_date = data["start_date"]
    shift, lesson_time = data.get("shift"), data.get("lesson_time")
    students_raw = data.get("students_raw") or []

    lines = [
        "<b>Проверь и подтверди</b>\n",
        f"Группа: <b>{name}</b>"
        + (" (существующая — данные обновятся)" if data.get("existing_group_id") else " (новая)"),
        f"Старт: {start_date}{_monday_warning(start_date)}",
        f"Смена: {_shift_label(shift, lesson_time)}",
        "",
        _preview_schedule(start_date, shift, lesson_time),
        "",
        f"Учеников к добавлению: {len(students_raw)}",
    ]
    await message.answer("\n".join(filter(None, lines)), reply_markup=kb.setup_confirm())


@router.callback_query(F.data == "su:restart", SetupWizard.confirm)
async def confirm_restart(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SetupWizard.name)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer("Начинаем заново")
    await call.message.answer("Шаг 1/4. Название группы?")


@router.callback_query(F.data == "su:done", SetupWizard.confirm)
async def confirm_done(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer("Сохраняю…")

    gid = await db.upsert_group(data["name"], data["start_date"],
                                data.get("lesson_time"), data.get("shift"))
    added = 0
    for full_name, class_school in (data.get("students_raw") or []):
        await db.add_student(gid, full_name, class_school)
        added += 1
    total = len(await db.students(gid))

    await state.clear()
    await call.message.answer(
        f"✅ Группа <b>{data['name']}</b> готова (id {gid}).\n"
        f"Добавлено учеников: {added}. Всего в группе: {total}.\n\n"
        "Дальше — <code>/invite</code>, чтобы прислать менторам ссылку, "
        "либо <code>/add_mentor</code> вручную."
    )
'''
