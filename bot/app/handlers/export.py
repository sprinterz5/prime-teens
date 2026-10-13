"""Выгрузка материалов для характеристик — основной способ забрать данные из бота."""
from __future__ import annotations

import datetime as dt
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app import db, dossier
from app.config import settings
from app.handlers.registration import is_admin

log = logging.getLogger(__name__)
router = Router(name="export")


async def _exportable_groups(tg_user_id: int) -> list | None:
    """Группы, материалы которых можно выгрузить, — в том числе завершённые:
    характеристики пишут после курса, а группа к тому времени уже закрыта
    (db.groups / mentor_groups по умолчанию их прячут). Ментор — свои группы,
    админ и курс-директор — все. None — человек не зарегистрирован."""
    mentor = await db.mentor_by_tg(tg_user_id)
    if not mentor:
        return None
    if await is_admin(tg_user_id) or mentor["is_director"]:
        return await db.groups(active_only=False)
    return await db.mentor_groups(mentor["id"], active_only=False)


async def _picker(groups: list) -> InlineKeyboardMarkup:
    """Сначала идущие группы, потом завершённые — свежие сверху."""
    active = {g["id"] for g in await db.groups()}
    current = [g for g in groups if g["id"] in active]
    finished = sorted((g for g in groups if g["id"] not in active),
                      key=lambda g: g["start_date"] or dt.date.min, reverse=True)
    rows = [[InlineKeyboardButton(text=g["name"], callback_data=f"ex:group:{g['id']}")] for g in current]
    rows += [[InlineKeyboardButton(text=f"🗂 {g['name']} · завершена", callback_data=f"ex:group:{g['id']}")]
             for g in finished]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text == "📤 Материалы")
@router.message(Command("export"))
async def entry(message: Message) -> None:
    groups = await _exportable_groups(message.from_user.id)
    if groups is None:
        await message.answer("Сначала зарегистрируйся: /start")
        return
    if not groups:
        await message.answer("К тебе не привязана группа.")
        return
    if len(groups) > 1:
        await message.answer("Какая группа?", reply_markup=await _picker(groups))
        return
    await _export(message, groups[0]["id"])


@router.callback_query(F.data.startswith("ex:group:"))
async def pick_group(call: CallbackQuery) -> None:
    gid = int(call.data.split(":")[2])
    groups = await _exportable_groups(call.from_user.id) or []
    if gid not in {g["id"] for g in groups}:
        await call.answer("Нет доступа к этой группе", show_alert=True)
        return
    await call.answer()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await _export(call.message, gid)


async def _export(message: Message, group_id: int) -> None:
    students = await db.students(group_id)
    if not students:
        await message.answer("В группе нет учеников.")
        return

    note = await message.answer("Собираю материалы…")
    try:
        zip_path, html_path, stats = await dossier.export_group(group_id)
    except Exception as e:  # noqa: BLE001
        log.exception("Выгрузка сорвалась")
        await note.edit_text(f"Не смог собрать выгрузку: {e}")
        return

    await note.delete()
    await message.answer_document(
        FSInputFile(html_path),
        caption=(
            "📄 <b>Все ученики в одном документе</b>\n"
            "Открывается в браузере. Заметки разложены по разделам характеристики — "
            "под каждым заголовком написано, куда он идёт.\n"
            "Печать → «Сохранить как PDF», если нужен PDF."
        ),
    )

    warn = ""
    if stats["empty"]:
        warn += f"\n⚠️ Без единой заметки: {', '.join(stats['empty'])}"
    if stats["final_done"] < stats["students"]:
        warn += (f"\n⚠️ Финальный опрос заполнен на {stats['final_done']} из "
                 f"{stats['students']} — без него не будет материала для разделов "
                 f"«Сильные стороны», «Заметный рост» и «Зоны роста». Это /final.")

    tail = ""
    if settings.experimental_characteristics:
        tail = ("\n\n🧪 Есть ещё экспериментальная автосборка характеристик — "
                "/characteristics. Черновик, всё написанное нужно перечитывать.")

    await message.answer_document(
        FSInputFile(zip_path),
        caption=(
            f"📦 <b>Полный пакет</b> · учеников {stats['students']}, "
            f"заметок {stats['notes']}\n\n"
            "• <code>vse_ucheniki.html</code> — то же, что выше\n"
            "• <code>ucheniki/*.md</code> — по файлу на ученика, удобно копировать\n"
            "• <code>svodnaya_tablica.csv</code> — посещаемость и включённость в Excel\n"
            "• <code>syrye_dannye.json</code> — то же машиночитаемо\n"
            "• <code>КАК_ПОЛЬЗОВАТЬСЯ.txt</code>"
            f"{warn}{tail}"
        ),
    )
