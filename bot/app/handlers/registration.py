"""Регистрация ментора по номеру телефона + базовые экраны."""
from __future__ import annotations

import datetime as dt
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app import db, keyboards as kb
from app.config import COURSE, settings

log = logging.getLogger(__name__)
router = Router(name="registration")

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class Registration(StatesGroup):
    """Между /start?start=inv_<token> и присланным контактом нужно пронести
    приглашение (токен, роль, для ментора — группу) — оно живёт тут, а не в
    roster (это не белый список, это одноразовая метка «этот заход — по
    ссылке»)."""
    invited = State()


def _role_badges(m) -> str:
    badges = ("👑" if m["is_admin"] else "") + ("🎓" if m["is_mentor"] else "")
    return badges or "·"


def _shift_label(g) -> str:
    """Смена группы человекочитаемо: ручной override lesson_time важнее смены.
    Формат (online/offline из ростера, если известен) добавляется в конец —
    на расчёт времени он не влияет, это чисто информационная пометка."""
    if g["lesson_time"]:
        label = f"занятия в {g['lesson_time']} (ручное время)"
    else:
        shift = COURSE["shifts"].get(g["shift"] or "evening", {})
        label = f"смена «{shift.get('label', g['shift'])}», начало {shift.get('start', '?')}"
    fmt = g["format"] if "format" in g.keys() else None
    if fmt:
        label += " · " + ("онлайн" if fmt == "online" else "оффлайн")
    return label


async def is_admin(tg_user_id: int) -> bool:
    if tg_user_id in settings.admin_ids:
        return True
    m = await db.mentor_by_tg(tg_user_id)
    return bool(m and m["is_admin"])


async def is_mentor(tg_user_id: int) -> bool:
    m = await db.mentor_by_tg(tg_user_id)
    return bool(m and m["is_mentor"])


async def _link_mentor_from_roster(mentor) -> str | None:
    """По номеру уже зарегистрированного ментора ищет запись в roster
    (заполняется Excel-импортом или /add_mentor) и привязывает группу оттуда.
    Возвращает название группы, если привязка удалась, иначе None — это и
    есть замена группы, которая раньше передавалась через саму ссылку."""
    if not mentor["phone"]:
        return None
    entry = await db.roster_lookup(mentor["phone"])
    if not entry or not entry["group_id"]:
        return None
    await db.link_mentor_group(mentor["id"], entry["group_id"])
    await db.set_mentor(mentor["tg_user_id"], True)
    g = await db.group(entry["group_id"])
    return g["name"] if g else None


@router.message(Command("whoami"))
async def whoami(message: Message) -> None:
    m = await db.mentor_by_tg(message.from_user.id)
    lines = [
        f"<b>Твой Telegram ID:</b> <code>{message.from_user.id}</code>",
        "Этот ID вписывается в <code>ADMIN_IDS</code> в .env, чтобы стать админом.",
    ]
    if m:
        groups = await db.mentor_groups(m["id"])
        lines.append(f"\nВ базе: {m['full_name']}, телефон {m['phone']}")
        lines.append("Группы: " + (", ".join(g["name"] for g in groups) or "нет"))
    await message.answer("\n".join(lines))


@router.message(CommandStart(deep_link=True))
async def start_invite(message: Message, command: CommandObject, state: FSMContext) -> None:
    """/start с пригласительной ссылкой (см. /invite в admin.py): t.me/<bot>?start=inv_<token>.
    Неизвестный или не inv_-payload — просто обычный /start, без сюрпризов.

    Все ссылки одноразовые (см. db.invite_status/claim_invite). Менторская
    ссылка (role='mentor') — просто пропуск в бота, без группы: group_id в
    записи invites для неё ничего не значит (см. комментарий в db.py),
    группа находится по номеру телефона в roster — см.
    _link_mentor_from_roster выше. Ссылка администратора (role='admin')
    устроена так же. Персональные ссылки учеников (student_id задан) ведут в
    отдельного, детского бота — сюда попасть не должны, но на всякий случай
    отклоняются понятным сообщением, а не тихо ломаются."""
    payload = (command.args or "").strip()
    if not payload.startswith("inv_"):
        await start(message)
        return

    token = payload[len("inv_"):]
    invite = await db.invite_by_token(token)
    status = await db.invite_status(token, message.from_user.id)

    if status in ("not_found", "revoked"):
        await message.answer(
            "Эта пригласительная ссылка недействительна или уже отозвана.\n"
            "Попроси у администратора новую, либо просто /start."
        )
        return
    if status == "used_by_other":
        await message.answer(
            "Эта ссылка уже использована — она одноразовая.\n"
            "Попроси у администратора новую, либо просто /start."
        )
        return
    if invite["student_id"] is not None:
        await message.answer(
            "Эта ссылка — для ученического бота, не для этого. "
            "Попроси у администратора верную ссылку."
        )
        return
    if status == "used_by_self":
        # уже проходил регистрацию по этой же ссылке раньше — не повторяем
        # церемонию, просто показываем обычный экран
        await start(message)
        return

    mentor = await db.mentor_by_tg(message.from_user.id)

    if invite["role"] == "admin":
        if mentor:
            claimed = await db.claim_invite(token, message.from_user.id)
            if claimed == "used_by_other":
                await message.answer("Пока ты открывал ссылку, её успели использовать.")
                return
            await db.set_admin(mentor["tg_user_id"], True)
            await message.answer(
                "Готово — теперь у тебя есть права администратора.",
                reply_markup=kb.main_menu(True, bool(mentor["is_mentor"])),
            )
            return
        await state.update_data(invite_token=token, invite_role="admin")
        await state.set_state(Registration.invited)
        await message.answer(
            "<b>PrimeTeens · бот ментора</b>\n\n"
            "Приглашение с правами администратора. Подтверди номер телефона.",
            reply_markup=kb.share_phone(),
        )
        return

    # role == "mentor" — одноразовый пропуск в бота, без группы (см. docstring выше)
    if mentor:
        claimed = await db.claim_invite(token, message.from_user.id)
        if claimed == "used_by_other":
            await message.answer("Пока ты открывал ссылку, её успели использовать.")
            return
        linked = await _link_mentor_from_roster(mentor)
        await message.answer(
            (f"Готово — по твоему номеру нашёл группу <b>{linked}</b>." if linked else
             "Готово. Пока твой номер не в списке — как только админ добавит "
             "его (Excel-импорт или /add_mentor), группа подтянется сама."),
            reply_markup=kb.main_menu(await is_admin(message.from_user.id),
                                      await is_mentor(message.from_user.id)),
        )
        return

    await state.update_data(invite_token=token, invite_role="mentor")
    await state.set_state(Registration.invited)
    await message.answer(
        "<b>PrimeTeens · бот ментора</b>\n\n"
        "Приглашение ментора. Подтверди номер телефона — по нему найду твою "
        "группу в списке, который загрузил админ.",
        reply_markup=kb.share_phone(),
    )


@router.message(CommandStart())
async def start(message: Message) -> None:
    mentor = await db.mentor_by_tg(message.from_user.id)
    if mentor:
        if mentor["is_mentor"]:
            groups = await db.mentor_groups(mentor["id"])
            names = ", ".join(g["name"] for g in groups) or "группа пока не назначена"
            text = f"С возвращением, {mentor['full_name']}.\nТвои группы: <b>{names}</b>"
        else:
            text = f"С возвращением, {mentor['full_name']}. Ты администратор без своей группы."
        await message.answer(
            text,
            reply_markup=kb.main_menu(await is_admin(message.from_user.id),
                                      bool(mentor["is_mentor"])),
        )
        return

    await message.answer(
        "<b>PrimeTeens · бот ментора</b>\n\n"
        "Я напоминаю о занятиях, после занятия провожу чек-лист по группе и по каждому "
        "ученику, а в конце курса собираю из этих заметок характеристики.\n\n"
        "Чтобы начать, подтверди номер телефона — по нему я найду тебя в списке менторов "
        "и подключу к твоей группе. Номер никуда не уходит, он только сверяется со списком.",
        reply_markup=kb.share_phone(),
    )


@router.message(F.contact)
async def got_contact(message: Message, state: FSMContext) -> None:
    contact = message.contact
    if contact.user_id != message.from_user.id:
        await message.answer(
            "Это чужой контакт. Нужен именно твой номер — нажми кнопку «Поделиться номером».",
            reply_markup=kb.share_phone(),
        )
        return

    phone = db.norm_phone(contact.phone_number)

    # Пришёл по пригласительной ссылке — регистрируем сразу (группа или права
    # администратора — по роли ссылки), без сверки с roster (белым списком).
    # /add_mentor при этом не трогаем — это отдельный, полностью рабочий путь
    # для ручного добавления.
    invite_data = await state.get_data()
    invite_token = invite_data.get("invite_token")
    if invite_token:
        invite_role = invite_data.get("invite_role", "mentor")
        await state.clear()

        status = await db.invite_status(invite_token, message.from_user.id)
        if status in ("not_found", "revoked"):
            await message.answer(
                "Пока ты нажимал «Поделиться номером», ссылку успели отозвать.\n"
                "Попроси у администратора новую, либо команду /add_mentor.",
                reply_markup=kb.REMOVE,
            )
            return
        if status == "used_by_other":
            await message.answer(
                "Пока ты нажимал «Поделиться номером», ссылку успели использовать.\n"
                "Попроси у администратора новую.",
                reply_markup=kb.REMOVE,
            )
            return

        full_name = " ".join(filter(None, [contact.first_name, contact.last_name])) or "Ментор"

        if invite_role == "admin":
            await db.claim_invite(invite_token, message.from_user.id)
            await db.register_mentor(message.from_user.id, phone, full_name,
                                     is_admin=True, is_mentor=False)
            await message.answer(
                f"Готово, {full_name}. Ты — <b>администратор</b>. Группу вести не обязан.",
                reply_markup=kb.main_menu(True, await is_mentor(message.from_user.id)),
            )
            return

        # role == "mentor": ссылка одноразовая — помечаем использованной.
        # Группа не в ссылке — ищем по номеру в roster (заполняется
        # Excel-импортом или /add_mentor). Нет в roster — регистрируем
        # ментором без группы, ждём, пока админ его добавит.
        await db.claim_invite(invite_token, message.from_user.id)
        mentor_id = await db.register_mentor(message.from_user.id, phone, full_name)
        entry = await db.roster_lookup(phone)
        if entry and entry["group_id"]:
            await db.link_mentor_group(mentor_id, entry["group_id"])
            g = await db.group(entry["group_id"])
            students = await db.students(entry["group_id"])
            roster_txt = "\n".join(f"  {i}. {s['full_name']}" for i, s in enumerate(students, 1))
            tail = f"\n\n<b>Твои ученики ({len(students)}):</b>\n{roster_txt}" if students else \
                "\n\nСписок учеников ещё не загружен — админ добавит его Excel-импортом или /add_students."
            await message.answer(
                f"Готово, {full_name}. Группа: <b>{g['name']}</b>.{tail}",
                reply_markup=kb.main_menu(await is_admin(message.from_user.id),
                                          await is_mentor(message.from_user.id)),
            )
        else:
            await message.answer(
                f"Готово, {full_name}. Твоего номера пока нет в списке — попроси "
                "администратора добавить его (Excel-импорт или /add_mentor), и "
                "группа подтянется сама.",
                reply_markup=kb.main_menu(await is_admin(message.from_user.id),
                                          await is_mentor(message.from_user.id)),
            )
        return

    entry = await db.roster_lookup(phone)
    admin_by_env = message.from_user.id in settings.admin_ids
    # Первый запуск: база пуста, значит это тот, кто бота и поднял.
    bootstrap = not entry and not admin_by_env and await db.is_first_run()

    if not entry and not admin_by_env and not bootstrap:
        await message.answer(
            f"Номер <code>+{phone}</code> не нашёлся в списке менторов.\n\n"
            "Попроси администратора добавить тебя — ему нужна команда:\n"
            f"<code>/add_mentor +{phone} Имя Фамилия | Название группы</code>",
            reply_markup=kb.REMOVE,
        )
        return

    full_name = (entry["full_name"] if entry else None) or \
        " ".join(filter(None, [contact.first_name, contact.last_name])) or "Ментор"
    # is_mentor из roster (Excel: роль "админ" без "ментор" даёт 0) — если
    # записи в roster нет вовсе (админ по ADMIN_IDS или bootstrap), по
    # умолчанию True, как и раньше.
    mentor_id = await db.register_mentor(
        message.from_user.id, phone, full_name,
        is_admin=admin_by_env or bootstrap or bool(entry and entry["is_admin"]),
        is_mentor=bool(entry["is_mentor"]) if entry is not None else True,
    )

    if bootstrap:
        log.warning("Первый запуск: %s (tg=%s) стал администратором",
                    full_name, message.from_user.id)
        await message.answer(
            f"Ты первый, кто пришёл — сделал тебя <b>администратором</b>.\n\n"
            f"Твой Telegram ID: <code>{message.from_user.id}</code>. "
            "Впиши его в <code>ADMIN_IDS</code> в <code>.env</code>, чтобы права "
            "не потерялись, если база когда-нибудь пересоздастся.\n\n"
            "Дальше настраиваем курс — /admin покажет все команды.",
            reply_markup=kb.main_menu(is_admin=True, is_mentor=True),
        )
        return

    group_name = "не назначена"
    if entry and entry["group_id"]:
        await db.link_mentor_group(mentor_id, entry["group_id"])
        g = await db.group(entry["group_id"])
        group_name = g["name"]
        students = await db.students(entry["group_id"])
        roster = "\n".join(f"  {i}. {s['full_name']}" for i, s in enumerate(students, 1))
        tail = f"\n\n<b>Твои ученики ({len(students)}):</b>\n{roster}" if students else \
            "\n\nСписок учеников ещё не загружен — админ добавит его командой /add_students."
    else:
        tail = "\n\nГруппа пока не назначена — напиши администратору."

    await message.answer(
        f"Готово, {full_name}. Группа: <b>{group_name}</b>.{tail}",
        reply_markup=kb.main_menu(await is_admin(message.from_user.id),
                                  await is_mentor(message.from_user.id)),
    )


async def _find_mentor_by_arg(arg: str):
    """Общий разбор аргумента /make_admin и /make_mentor: телефон или tg id."""
    target = None
    if arg.lstrip("+").isdigit() and len(db.norm_phone(arg)) >= 10:
        target = await db.mentor_by_phone(arg)
    if target is None and arg.isdigit():
        target = await db.mentor_by_tg(int(arg))
    return target


@router.message(Command("make_admin"))
async def make_admin(message: Message, command: CommandObject) -> None:
    """Выдать права администратора уже зарегистрированному пользователю."""
    if not await is_admin(message.from_user.id):
        await message.answer("Команда только для администратора.")
        return
    arg = (command.args or "").strip()
    if not arg:
        mentors = await db.q("SELECT tg_user_id, phone, full_name, is_admin, is_mentor FROM mentors")
        who = "\n".join(
            f"  {_role_badges(m)} {m['full_name']} · +{m['phone']} · "
            f"<code>{m['tg_user_id']}</code>" for m in mentors
        ) or "  (пока никого)"
        await message.answer(
            "Формат: <code>/make_admin +77011234567</code> или "
            "<code>/make_admin 123456789</code> (Telegram ID)\n\n"
            f"👑 админ · 🎓 ментор\n\nКто уже зарегистрирован:\n{who}"
        )
        return

    target = await _find_mentor_by_arg(arg)
    if target is None:
        await message.answer(
            "Не нашёл такого среди зарегистрированных. Он должен сперва сам "
            "написать боту /start и поделиться номером."
        )
        return

    await db.set_admin(target["tg_user_id"], True)
    await message.answer(f"👑 {target['full_name']} теперь администратор.")


@router.message(Command("make_mentor"))
async def make_mentor(message: Message, command: CommandObject) -> None:
    """Выдать роль ментора уже зарегистрированному пользователю (например,
    админу-организатору, который решил ещё и вести группу)."""
    if not await is_admin(message.from_user.id):
        await message.answer("Команда только для администратора.")
        return
    arg = (command.args or "").strip()
    if not arg:
        mentors = await db.q("SELECT tg_user_id, phone, full_name, is_admin, is_mentor FROM mentors")
        who = "\n".join(
            f"  {_role_badges(m)} {m['full_name']} · +{m['phone']} · "
            f"<code>{m['tg_user_id']}</code>" for m in mentors
        ) or "  (пока никого)"
        await message.answer(
            "Формат: <code>/make_mentor +77011234567</code> или "
            "<code>/make_mentor 123456789</code> (Telegram ID)\n\n"
            f"👑 админ · 🎓 ментор\n\nКто уже зарегистрирован:\n{who}"
        )
        return

    target = await _find_mentor_by_arg(arg)
    if target is None:
        await message.answer(
            "Не нашёл такого среди зарегистрированных. Он должен сперва сам "
            "написать боту /start и поделиться номером."
        )
        return

    await db.set_mentor(target["tg_user_id"], True)
    await message.answer(f"🎓 {target['full_name']} теперь ментор.")


@router.message(F.text == "👥 Моя группа")
@router.message(Command("group"))
async def my_group(message: Message) -> None:
    mentor = await db.mentor_by_tg(message.from_user.id)
    if not mentor:
        await message.answer("Сначала зарегистрируйся: /start")
        return
    groups = await db.mentor_groups(mentor["id"])
    if not groups:
        await message.answer("К тебе пока не привязана ни одна группа.")
        return
    chunks = []
    for g in groups:
        students = await db.students(g["id"])
        mentors = await db.group_mentors(g["id"])
        lines = [
            f"<b>{g['name']}</b>",
            f"Старт: {g['start_date'] or '—'} · {_shift_label(g)}",
            f"Менторы: {', '.join(m['full_name'] for m in mentors)}",
            f"\nУченики ({len(students)}):",
        ]
        lines += [f"  {i}. {s['full_name']}"
                  f"{' · ' + s['team'] if s['team'] else ''}"
                  for i, s in enumerate(students, 1)]
        chunks.append("\n".join(lines))
    await message.answer("\n\n".join(chunks))


async def _send_chunks(message: Message, lines: list[str], limit: int = 3500) -> None:
    """Разбивает длинный текст на несколько сообщений — Telegram режет
    примерно на 4096 символах, лимит взят с запасом."""
    buf: list[str] = []
    size = 0
    for line in lines:
        if size + len(line) + 1 > limit and buf:
            await message.answer("\n".join(buf))
            buf, size = [], 0
        buf.append(line)
        size += len(line) + 1
    if buf:
        await message.answer("\n".join(buf))


@router.message(Command("feedback"))
async def feedback_summary(message: Message) -> None:
    """Отзывы учеников по своим группам. Анонимно ПО ПОЛИТИКЕ: запрос
    (db.group_kid_feedback) физически не отдаёт имя ученика — тут его
    негде взять, даже если очень захотеть."""
    mentor = await db.mentor_by_tg(message.from_user.id)
    if not mentor:
        await message.answer("Сначала зарегистрируйся: /start")
        return
    groups = await db.mentor_groups(mentor["id"])
    if not groups:
        await message.answer("К тебе пока не привязана ни одна группа.")
        return

    for g in groups:
        rows = await db.group_kid_feedback(g["id"])
        if not rows:
            await message.answer(f"<b>{g['name']}</b>\nОтзывов пока нет.")
            continue

        stats = await db.kid_feedback_stats(g["id"])
        lines = [f"<b>{g['name']}</b>"]
        for day in sorted(stats):
            s = stats[day]
            avg = f"{s['avg']:.1f}" if s["avg"] is not None else "—"
            title = COURSE["days"][day - 1]["title"] if 1 <= day <= len(COURSE["days"]) \
                else f"день {day}"
            lines.append(f"\n<b>День {day} — {title}</b> · отзывов {s['count']} · средняя {avg}")
            for r in rows:
                if r["day_index"] != day or not r["text"]:
                    continue
                tag = " 🎙" if r["source"] == "voice" else ""
                rating = f"{r['rating']}⭐ " if r["rating"] is not None else ""
                lines.append(f"  {rating}{r['text']}{tag}")
        await _send_chunks(message, lines)


@router.message(F.text == "🗓 Расписание")
@router.message(Command("schedule"))
async def schedule(message: Message) -> None:
    mentor = await db.mentor_by_tg(message.from_user.id)
    if not mentor:
        await message.answer("Сначала зарегистрируйся: /start")
        return
    groups = await db.mentor_groups(mentor["id"])
    if not groups:
        await message.answer("К тебе пока не привязана ни одна группа.")
        return

    now = dt.datetime.now(settings.tz)
    out = []
    for g in groups:
        lines = [f"<b>{g['name']}</b> · {_shift_label(g)}"]
        if not g["start_date"]:
            lines.append("Дата старта не задана — админ ставит её командой /set_start.")
            out.append("\n".join(lines))
            continue
        for d in COURSE["days"]:
            window = await db.group_lesson_window(g["id"], d["index"])
            if window is None:
                continue
            when, end = window
            kind = "hackathon" if d.get("hackathon") else "lesson"
            done = await db.session_done(g["id"], d["index"], kind)
            mark = "✅" if done else ("▶️" if when.date() == now.date() else
                                     ("· " if when > now else "◻️"))
            lines.append(
                f"{mark} <b>День {d['index']}</b> · {WEEKDAYS[when.weekday()]} "
                f"{when.strftime('%d.%m')} {when.strftime('%H:%M')}–{end.strftime('%H:%M')} "
                f"— {d['title']}"
            )
            for t0, t1, name in db.day_block_times(d, when):
                lines.append("      " + db.fmt_block(t0, t1, name))
        lines.append("\n✅ чек-лист заполнен · ◻️ прошло, чек-листа нет · ▶️ сегодня")
        out.append("\n".join(lines))
    await message.answer("\n\n".join(out))


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    text = (
        "<b>Что я умею</b>\n\n"
        "/start — регистрация по номеру\n"
        "/schedule — расписание твоей группы\n"
        "/group — состав группы\n"
        "/checklist — заполнить чек-лист (за сегодня или за любой день)\n"
        "/final — финальный опрос перед характеристиками\n"
        "/export — выгрузить материалы для характеристик\n"
        "/feedback — отзывы учеников по своим группам (из детского бота, без имён)\n"
        "/whoami — мой Telegram ID\n\n"
        "На вопросы чек-листа можно отвечать <b>голосовым</b> — я расшифрую сам."
    )
    if settings.experimental_characteristics:
        text += ("\n\n🧪 /characteristics — черновик характеристик моделью. "
                 "Эксперимент: всё написанное нужно перечитывать перед показом родителям.")
    if await is_admin(message.from_user.id):
        text += (
            "\n\n<b>Админ:</b>\n"
            "/template — шаблон Excel (Группы / Менторы / Ученики)\n"
            "пришли заполненный .xlsx боту — группы, менторы и ученики подтянутся сами\n"
            "/add_mentor +77011234567 Имя Фамилия | Группа\n"
            "/invite — меню ссылок: ментору (одноразовый пропуск), ученикам, админу\n"
            "/groups (или /groups all) — активные группы (или вообще все)\n"
            "/students, /today, /overview — сводки по курсу\n"
            "/make_admin, /make_mentor +номер — выдать роль\n"
            "/broadcast текст — сообщение всем менторам\n"
            "/admin_manual — ручной режим (если в экселе ошибка)"
        )
    await message.answer(text)
