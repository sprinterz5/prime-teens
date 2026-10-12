"""Ссылки на веб-платформу (тетрадь, домашка, кабинет ментора) — общие для
обоих ботов. Сама платформа — Next.js в корне репозитория; боты только
выдают вход (/login) и присылают ссылки в уведомлениях."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app import db
from app.config import settings

NOT_CONFIGURED = "Платформа пока не подключена — напиши организаторам."


def url(path: str = "/") -> str | None:
    """Полный адрес страницы платформы, None — если PLATFORM_URL не задан."""
    if not settings.platform_url:
        return None
    return settings.platform_url + path


def link_line(label: str, path: str) -> str:
    """Строка со ссылкой для текста уведомления; пустая без PLATFORM_URL."""
    full = url(path)
    return f'\n{label}: <a href="{full}">{full}</a>' if full else ""


def _button(text: str, full_url: str) -> InlineKeyboardMarkup | None:
    # Telegram принимает в кнопках только https — локальный http-адрес
    # (разработка) остаётся ссылкой в тексте.
    if not full_url.startswith("https://"):
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, url=full_url)]])


async def login_message(role: str, tg_user_id: int, *, student_id: int | None = None,
                        mentor_id: int | None = None) -> tuple[str, InlineKeyboardMarkup | None]:
    """Текст и кнопка для /login. Ссылка одноразовая: открывать в браузере,
    где человек будет работать, и никому не пересылать."""
    if not settings.platform_url:
        return NOT_CONFIGURED, None
    token, code = await db.issue_login_code(
        role, tg_user_id, student_id=student_id, mentor_id=mentor_id,
    )
    link = f"{settings.platform_url}/login/{token}"
    login_page = f"{settings.platform_url}/login"
    markup = _button("💻 Войти на платформу", link)
    text = (
        "<b>Вход на платформу</b>\n\n"
        + ("Нажми кнопку ниже" if markup else f'Открой ссылку: <a href="{link}">{link}</a>')
        + " — откроется в браузере, и ты сразу внутри.\n\n"
        f"Или открой <a href=\"{login_page}\">{login_page}</a> на компьютере "
        f"и введи код: <code>{code}</code>\n\n"
        f"Ссылка и код одноразовые и действуют {db.LOGIN_TTL_MINUTES} минут. "
        "Никому их не пересылай — это вход в твой аккаунт."
    )
    return text, markup
