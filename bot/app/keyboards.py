"""Клавиатуры."""
from __future__ import annotations

from typing import Any, Iterable

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.config import settings

REMOVE = ReplyKeyboardRemove()


def share_phone() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Нажми кнопку ниже",
    )


def main_menu(is_admin: bool, is_mentor: bool = True) -> ReplyKeyboardMarkup:
    """is_admin и is_mentor независимы (см. app/db.py: mentors.is_admin/is_mentor).
    Чисто административный организатор без своей группы не должен видеть
    менторские кнопки — у него их просто нет, а не пустое меню под ними."""
    rows: list[list[KeyboardButton]] = []
    if is_mentor:
        rows.append([KeyboardButton(text="📝 Чек-лист"), KeyboardButton(text="🗓 Расписание")])
        rows.append([KeyboardButton(text="👥 Моя группа"), KeyboardButton(text="📤 Материалы")])
        if settings.experimental_characteristics:
            rows.append([KeyboardButton(text="🧪 Характеристики (эксперимент)")])
    if is_admin:
        rows.append([KeyboardButton(text="⚙️ Админка")])
    if not rows:
        # ни одной роли — такого быть не должно, но без этого Telegram не
        # примет пустую клавиатуру
        rows.append([KeyboardButton(text="ℹ️ /help")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def start_checklist(group_id: int, day_index: int, kind: str = "lesson") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Погнали",
                             callback_data=f"ck:start:{group_id}:{day_index}:{kind}"),
        InlineKeyboardButton(text="⏰ Позже",
                             callback_data=f"ck:later:{group_id}:{day_index}:{kind}"),
    ]])


def scale(labels: dict[str, str] | None = None) -> InlineKeyboardMarkup:
    labels = labels or {}
    row = [
        InlineKeyboardButton(text=str(i), callback_data=f"ck:scale:{i}")
        for i in range(1, 6)
    ]
    kb = [row, [InlineKeyboardButton(text="⏹ Прервать", callback_data="ck:stop")]]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def choice(options: list[dict], skippable: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=o["label"], callback_data=f"ck:opt:{o['value']}")]
        for o in options
    ]
    tail = []
    if skippable:
        tail.append(InlineKeyboardButton(text="➡️ Пропустить", callback_data="ck:skip"))
    tail.append(InlineKeyboardButton(text="⏹ Прервать", callback_data="ck:stop"))
    rows.append(tail)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def text_answer(skippable: bool) -> InlineKeyboardMarkup:
    row = []
    if skippable:
        row.append(InlineKeyboardButton(text="➡️ Пропустить", callback_data="ck:skip"))
    row.append(InlineKeyboardButton(text="⏹ Прервать", callback_data="ck:stop"))
    return InlineKeyboardMarkup(inline_keyboard=[row])


def students_multi(students: Iterable[Any], selected: set[int],
                   empty_label: str = "— никто") -> InlineKeyboardMarkup:
    """Мультивыбор одним экраном — главное условие скорости опроса.
    Восемь учеников = один экран, а не восемь отдельных вопросов."""
    rows, row = [], []
    for st in students:
        mark = "☑️" if st["id"] in selected else "▫️"
        name = st["short_name"] or st["full_name"]
        row.append(InlineKeyboardButton(text=f"{mark} {name}",
                                        callback_data=f"ck:stu:{st['id']}"))
        if len(row) == 2:            # два в ряд: имена помещаются, экран короче
            rows.append(row); row = []
    if row:
        rows.append(row)
    if selected:
        rows.append([InlineKeyboardButton(text=f"✅ Готово ({len(selected)})",
                                          callback_data="ck:stu_done")])
    else:
        rows.append([InlineKeyboardButton(text=empty_label, callback_data="ck:stu_none")])
    rows.append([InlineKeyboardButton(text="⏹ Прервать", callback_data="ck:stop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tags_multi(tags: list[dict], selected: set[str]) -> InlineKeyboardMarkup:
    rows, row = [], []
    for t in tags:
        mark = "☑️" if t["code"] in selected else "▫️"
        row.append(InlineKeyboardButton(text=f"{mark} {t['label']}",
                                        callback_data=f"ck:tag:{t['code']}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(
        text=f"✅ Готово ({len(selected)})" if selected else "➡️ Ничего из этого",
        callback_data="ck:tag_done")])
    rows.append([InlineKeyboardButton(text="⏹ Прервать", callback_data="ck:stop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def scale10(previous: int | None = None) -> InlineKeyboardMarkup:
    """0..10 двумя рядами. Если есть стартовая оценка — она подсвечена."""
    def cell(i: int) -> InlineKeyboardButton:
        mark = "•" if previous is not None and i == previous else ""
        return InlineKeyboardButton(text=f"{mark}{i}{mark}",
                                    callback_data=f"ck:s10:{i}")
    return InlineKeyboardMarkup(inline_keyboard=[
        [cell(i) for i in range(0, 6)],
        [cell(i) for i in range(6, 11)],
        [InlineKeyboardButton(text="⏹ Прервать", callback_data="ck:stop")],
    ])


def voice_saved(answer_id: int) -> InlineKeyboardMarkup:
    """Ответ уже сохранён — кнопка на случай, если расшифровка кривая.
    Живёт на старом сообщении: можно вернуться и переписать позже."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Переписать", callback_data=f"ck:fix:{answer_id}")
    ]])


def voice_confirm() -> InlineKeyboardMarkup:
    """Спрашиваем до сохранения — режим confirm: always или сомнительная расшифровка."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Сохранить", callback_data="ck:vok"),
        InlineKeyboardButton(text="🔄 Переписать", callback_data="ck:vredo"),
    ]])


def pick_group(groups: Iterable[Any], prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=g["name"], callback_data=f"{prefix}:{g['id']}")]
        for g in groups
    ])


def pick_day(group_id: int, days: list[dict], kind: str = "lesson") -> InlineKeyboardMarkup:
    rows, row = [], []
    for d in days:
        row.append(InlineKeyboardButton(
            text=f"День {d['index']}",
            callback_data=f"ck:start:{group_id}:{d['index']}:{kind}",
        ))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(
        text="🏁 Финальный опрос (характеристики)",
        callback_data=f"ck:start:{group_id}:0:final",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def setup_similar(existing_id: int, existing_name: str) -> InlineKeyboardMarkup:
    """Похожая группа уже есть — /setup спрашивает, опечатка это или нет."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"Это она: «{existing_name}»",
                             callback_data=f"su:same:{existing_id}"),
        InlineKeyboardButton(text="➕ Создать новую", callback_data="su:new"),
    ]])


def setup_mondays(options: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """options — [(подпись, ISO-дата), …], обычно ближайшие 3 понедельника."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=f"su:date:{iso}")]
        for label, iso in options
    ])


def setup_shift(morning_label: str, evening_label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=morning_label, callback_data="su:shift:morning"),
         InlineKeyboardButton(text=evening_label, callback_data="su:shift:evening")],
        [InlineKeyboardButton(text="🕐 Другое время", callback_data="su:shift:custom")],
    ])


def setup_skip_students() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➡️ Пропустить, добавлю позже",
                             callback_data="su:skip_students"),
    ]])


def setup_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Готово", callback_data="su:done"),
        InlineKeyboardButton(text="🔄 Начать заново", callback_data="su:restart"),
    ]])


def invite_revoke(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚫 Отозвать", callback_data=f"inv:revoke:{token}"),
    ]])


def invite_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑‍🏫 Ссылка для ментора", callback_data="inv:menu:mentor")],
        [InlineKeyboardButton(text="🎓 Ссылки для учеников", callback_data="inv:menu:students")],
        [InlineKeyboardButton(text="👑 Ссылка для админа", callback_data="inv:menu:admin")],
    ])


def pick_students(students: Iterable[Any], prefix: str,
                  extra_all: str | None = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=st["full_name"], callback_data=f"{prefix}:{st['id']}")]
        for st in students
    ]
    if extra_all:
        rows.insert(0, [InlineKeyboardButton(text="📦 Все сразу", callback_data=extra_all)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
