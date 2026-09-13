"""Клавиатуры детского бота."""
from __future__ import annotations

from typing import Any, Iterable

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

REMOVE = ReplyKeyboardRemove()


def share_phone() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Нажми кнопку ниже",
    )


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🗓 Расписание"), KeyboardButton(text="💬 Отзыв об уроке")],
            [KeyboardButton(text="🏆 Моя команда")],
        ],
        resize_keyboard=True,
    )


def pick_self(matches: Iterable[Any]) -> InlineKeyboardMarkup:
    """Телефон совпал с несколькими учениками (семейный номер) — пусть
    выберет себя сам."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{s['full_name']} · {s['group_name']}",
                              callback_data=f"me:{s['id']}")]
        for s in matches
    ])


def rating() -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=f"{i}⭐", callback_data=f"fb:rate:{i}") for i in range(1, 6)]
    return InlineKeyboardMarkup(inline_keyboard=[row])


def feedback_skip_comment() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➡️ Без комментария", callback_data="fb:skip"),
    ]])


def team_entry() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏁 Создать команду", callback_data="team:create")],
        [InlineKeyboardButton(text="🔑 У меня есть код от капитана", callback_data="team:join")],
    ])


def team_skip_case() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➡️ Пока без кейса", callback_data="team:skip_case"),
    ]])


def team_card(join_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚪 Выйти из команды", callback_data="team:leave"),
    ]])
