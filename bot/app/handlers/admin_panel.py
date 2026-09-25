"""Кнопочная админка: «⚙️ Админка» / /admin открывает меню, всё остальное —
кнопками, без запоминания команд. Отчёты переиспользуют хендлеры admin.py
(команды по-прежнему работают), здесь только навигация и короткие диалоги:
добавить админа/ментора по номеру и рассылка менторам с подтверждением."""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, InlineKeyboardButton as B,
                           InlineKeyboardMarkup, Message)

from app import db, keyboards as kb
from app.config import settings
from app.handlers import admin
from app.handlers.registration import is_admin

log = logging.getLogger(__name__)
router = Router(name="admin_panel")


class Panel(StatesGroup):
    admin_phone = State()
    mentor_phone = State()
    broadcast_text = State()


def _markup(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [B(text=t, callback_data=d) for t, d in row] for row in rows])


BACK = [("‹ Назад", "ap:home")]
CANCEL = _markup([[("✖️ Отмена", "ap:home")]])

HOME_TEXT = "<b>⚙️ Админка</b>\nВыбери, что нужно — всё кнопками."
HOME = _markup([
    [("📅 Сегодня", "ap:r:today"), ("📊 Сводка", "ap:r:overview")],
    [("👥 Группы", "ap:r:groups"), ("🧑‍🎓 Ученики", "ap:r:students")],
    [("✅ Заполненность опросов", "ap:r:stats")],
    [("🙋 Люди и доступ", "ap:people")],
    [("📥 Загрузить списки", "ap:data")],
    [("📣 Написать менторам", "ap:bc")],
    [("📖 Все команды", "ap:help")],
])


def _as_admin(call: CallbackQuery) -> Message:
    """Сообщение с меню, но от имени нажавшего — чтобы переиспользовать
    хендлеры admin.py, которые проверяют message.from_user."""
    return call.message.model_copy(update={"from_user": call.from_user})


async def _show(call: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    try:
        await call.message.edit_text(text, reply_markup=markup)
    except Exception:  # то же самое содержимое или сообщение слишком старое
        await call.message.answer(text, reply_markup=markup)


@router.message(F.text == "⚙️ Админка")
@router.message(Command("admin"))
async def open_panel(message: Message, state: FSMContext) -> None:
    if not await is_admin(message.from_user.id):
        await message.answer("Это только для администратора.")
        return
    await state.clear()
    await message.answer(HOME_TEXT, reply_markup=HOME)


@router.callback_query(F.data.startswith("ap:"))
async def panel_guard(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not await is_admin(call.from_user.id):
        await call.answer("Только для администратора", show_alert=True)
        return
    action = call.data[3:]
    await call.answer()

    if action == "home":
        await state.clear()
        await _show(call, HOME_TEXT, HOME)
    elif action.startswith("r:"):
        await _report(action[2:], _as_admin(call))
    elif action == "people":
        await _show(call, await _people_text(), _markup([
            [("👑 Добавить админа", "ap:add_admin")],
            [("🎓 Добавить ментора", "ap:add_mentor")],
            [("🔗 Ссылка-приглашение", "ap:invite")],
            BACK,
        ]))
    elif action == "add_admin":
        await state.set_state(Panel.admin_phone)
        await _show(call, "<b>👑 Новый админ</b>\n\nПришли номер и имя одним сообщением:\n"
                          "<code>+77011234567 Имя Фамилия</code>", CANCEL)
    elif action == "add_mentor":
        if not await db.groups():
            await _show(call, "Активных групп нет — сначала загрузи списки.", _markup([BACK]))
            return
        await state.set_state(Panel.mentor_phone)
        await _show(call, "<b>🎓 Новый ментор</b>\n\nПришли номер и имя одним сообщением:\n"
                          "<code>+77011234567 Имя Фамилия</code>\n\nГруппу выберешь следующим шагом.",
                    CANCEL)
    elif action.startswith("mgroup:"):
        await _mentor_group(call, state, int(action[7:]))
    elif action == "invite":
        await _show(call, "Какую ссылку сделать?", kb.invite_menu())
    elif action == "data":
        rows = [[("📄 Скачать шаблон Excel", "ap:template")]]
        if settings.sheets_sync_url:
            rows.append([("🔄 Подтянуть из Google-таблицы", "ap:sync")])
        await _show(call, "<b>📥 Загрузить списки</b>\n\nЗаполни шаблон и пришли файл "
                          ".xlsx прямо в этот чат — группы, менторы и ученики "
                          "обновятся без дублей.", _markup(rows + [BACK]))
    elif action == "template":
        await admin.send_template(_as_admin(call))
    elif action == "sync":
        await admin.sync_sheet_cmd(_as_admin(call))
    elif action == "bc":
        await state.set_state(Panel.broadcast_text)
        await _show(call, "<b>📣 Сообщение всем менторам</b>\n\nНапиши текст — "
                          "перед отправкой покажу, как он выглядит.", CANCEL)
    elif action == "bc_send":
        await _broadcast_send(call, state, bot)
    elif action == "help":
        await admin.admin_help(_as_admin(call))


async def _report(name: str, msg: Message) -> None:
    empty = CommandObject(prefix="/", command=name)
    if name == "today":
        await admin.today_cmd(msg)
    elif name == "overview":
        await admin.overview_cmd(msg)
    elif name == "groups":
        await admin.list_groups(msg, empty)
    elif name == "students":
        await admin.students_cmd(msg)
    elif name == "stats":
        await admin.stats(msg)


async def _people_text() -> str:
    rows = await db.q("SELECT full_name, is_admin, is_mentor FROM mentors ORDER BY full_name")
    admins = [r["full_name"] for r in rows if r["is_admin"]]
    mentors = [r["full_name"] for r in rows if r["is_mentor"]]
    waiting = await db.q(
        "SELECT r.full_name FROM roster r LEFT JOIN mentors m ON m.phone = r.phone "
        "WHERE r.is_admin AND m.id IS NULL ORDER BY r.full_name")
    out = ["<b>🙋 Люди и доступ</b>", "",
           f"👑 Админы ({len(admins)}): " + (", ".join(admins) or "—")]
    if waiting:
        out.append("⏳ Ещё не зашли в бота: " + ", ".join(r["full_name"] for r in waiting))
    out.append(f"🎓 Менторов в боте: {len(mentors)}")
    return "\n".join(out)


def _parse_person(text: str) -> tuple[str, str] | None:
    """«+7 701 123 45 67 Имя Фамилия» → (номер, имя). Номер — все цифры до
    первого слова из букв."""
    words = text.split()
    i = 0
    while i < len(words) and not any(ch.isalpha() for ch in words[i]):
        i += 1
    phone = db.norm_phone(" ".join(words[:i]))
    name = " ".join(words[i:]).strip()
    if len(phone) < 10 or not name:
        return None
    return phone, name


@router.message(Panel.admin_phone, F.text)
async def add_admin_got(message: Message, state: FSMContext, bot: Bot) -> None:
    parsed = _parse_person(message.text)
    if not parsed:
        await message.answer("Не разобрал. Нужно так: <code>+77011234567 Имя Фамилия</code>",
                             reply_markup=CANCEL)
        return
    await state.clear()
    phone, name = parsed
    m = await db.grant_admin(phone, name)
    if m:
        try:
            await bot.send_message(
                m["tg_user_id"], "Тебе выдали права администратора — внизу появилась «⚙️ Админка».",
                reply_markup=kb.main_menu(True, bool(m["is_mentor"])))
        except Exception:
            log.warning("Не доставлено уведомление админу %s", m["tg_user_id"])
        text = f"👑 {m['full_name']} теперь админ — уже видит «⚙️ Админка»."
    else:
        text = (f"👑 {name} (+{phone}) записан как админ.\n"
                "Пусть откроет бота, нажмёт /start и поделится номером — права включатся сами.")
    await message.answer(text, reply_markup=_markup([[("🙋 К людям", "ap:people")], BACK]))


@router.message(Panel.mentor_phone, F.text)
async def add_mentor_got(message: Message, state: FSMContext) -> None:
    parsed = _parse_person(message.text)
    if not parsed:
        await message.answer("Не разобрал. Нужно так: <code>+77011234567 Имя Фамилия</code>",
                             reply_markup=CANCEL)
        return
    phone, name = parsed
    await state.update_data(phone=phone, name=name)
    groups = await db.groups()
    await message.answer(f"{name} (+{phone}) — в какую группу?",
                         reply_markup=_markup([[(g["name"], f"ap:mgroup:{g['id']}")] for g in groups]
                                              + [[("✖️ Отмена", "ap:home")]]))


async def _mentor_group(call: CallbackQuery, state: FSMContext, group_id: int) -> None:
    data = await state.get_data()
    await state.clear()
    if "phone" not in data:
        await _show(call, "Начни заново.", HOME)
        return
    g = await db.group(group_id)
    entry = await db.roster_lookup(data["phone"])
    await db.add_to_roster(data["phone"], data["name"], group_id,
                           is_admin=bool(entry and entry["is_admin"]))
    m = await db.mentor_by_phone(data["phone"])
    if m:
        await db.set_mentor(m["tg_user_id"], True)
        await db.link_mentor_group(m["id"], group_id)
        tail = "Он уже в боте — группа подключена."
    else:
        tail = "Пусть откроет бота, нажмёт /start и поделится номером."
    await _show(call, f"🎓 {data['name']} → группа <b>{g['name']}</b>.\n{tail}",
                _markup([[("🙋 К людям", "ap:people")], BACK]))


@router.message(Panel.broadcast_text, F.text)
async def broadcast_got(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.html_text)
    n = len(await db.q("SELECT 1 FROM mentors WHERE is_mentor"))
    await message.answer(f"Так увидят менторы ({n}):\n\n{message.html_text}",
                         reply_markup=_markup([[("✅ Отправить", "ap:bc_send")],
                                               [("✏️ Изменить", "ap:bc"), ("✖️ Отмена", "ap:home")]]))


async def _broadcast_send(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    text = (await state.get_data()).get("text")
    await state.clear()
    if not text:
        await _show(call, "Текст потерялся — начни заново.", HOME)
        return
    mentors = await db.q("SELECT tg_user_id FROM mentors WHERE is_mentor")
    sent = 0
    for m in mentors:
        try:
            await bot.send_message(m["tg_user_id"], text)
            sent += 1
        except Exception:
            log.warning("Не доставлено: %s", m["tg_user_id"])
    await _show(call, f"📣 Отправлено: {sent} из {len(mentors)}.", _markup([BACK]))
