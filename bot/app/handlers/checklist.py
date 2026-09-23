"""Опрос после урока, стартовый и финальный замер, блок хакатона.

Схема из ТЗ: спрашиваем по исключениям. Ментор отмечает только отклонения —
кого не было, кто отличился, у кого не шло, кто не сдал. Подвопросы
разворачиваются лишь на отмеченных. Про остальных не спрашивается ничего:
«урок прошёл ровно» — это тоже данные, и они стоили ноль нажатий.

Про нагрузку: бот спит на long polling и просыпается на входящий апдейт.
Нажатие инлайн-кнопки стоит ровно столько же, сколько обычное сообщение,
никаких циклов ожидания в коде нет.
"""
from __future__ import annotations

import datetime as dt
import logging
import time
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app import db, flow, keyboards as kb, stt
from app.config import COURSE, day_meta, settings

log = logging.getLogger(__name__)
router = Router(name="checklist")

KIND_TITLES = {
    "baseline": "📋 Стартовый замер",
    "lesson": "📝 Опрос после урока",
    "hackathon": "🏁 Блок хакатона",
    "final": "🎯 Финальный замер",
}


class Survey(StatesGroup):
    answering = State()
    editing = State()      # переписываем один уже сохранённый ответ


def _needs_confirm(tr: stt.Transcript, seconds: int | None = None) -> bool:
    """always — спрашивать всегда, smart — когда whisper не уверен или явно
    оборвался на середине, never — не спрашивать."""
    mode = (COURSE.get("voice") or {}).get("confirm", "smart")
    if mode == "always":
        return True
    if mode == "never":
        return False
    if tr.low:
        return True
    # Длинная запись с парой слов на выходе — почти всегда обрыв расшифровки.
    if seconds and seconds >= 10:
        words = len(tr.text.split())
        if words / seconds < 0.5:
            return True
    return False


# ----------------------------------------------------------------- вход

async def _mentor_or_none(user_id: int, message: Message):
    mentor = await db.mentor_by_tg(user_id)
    if not mentor:
        await message.answer("Сначала зарегистрируйся: /start")
    return mentor


def _today_day_index(start_date: dt.date | None) -> int | None:
    if not start_date:
        return None
    offset = (dt.datetime.now(settings.tz).date() - start_date).days
    for d in COURSE["days"]:
        if int(d["offset_days"]) == offset:
            return int(d["index"])
    return None


@router.message(F.text == "📝 Чек-лист")
@router.message(Command("checklist"))
async def checklist_entry(message: Message, state: FSMContext) -> None:
    await state.clear()
    mentor = await _mentor_or_none(message.from_user.id, message)
    if not mentor:
        return
    groups = await db.mentor_groups(mentor["id"])
    if not groups:
        await message.answer("К тебе не привязана группа — напиши админу.")
        return
    if len(groups) > 1:
        await message.answer("Какая группа?", reply_markup=kb.pick_group(groups, "ck:group"))
        return
    await _offer(message, groups[0], mentor["id"])


@router.callback_query(F.data.startswith("ck:group:"))
async def pick_group_cb(call: CallbackQuery) -> None:
    g = await db.group(int(call.data.split(":")[2]))
    mentor = await db.mentor_by_tg(call.from_user.id)
    if not mentor:
        await call.answer("Сначала /start", show_alert=True)
        return
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await _offer(call.message, g, mentor["id"])
    await call.answer()


async def _open_days(g, mentor_id: int) -> list[dict] | None:
    """Дни, которые этот ментор ещё может заполнить: занятие уже началось и
    свой опрос за день он не закрыл (не заполнил и не отметил «не вёл»).
    Чужие опросы не мешают — у каждого ментора свой. None — у группы нет даты старта."""
    if not g["start_date"]:
        return None
    now = dt.datetime.now(settings.tz)
    today = _today_day_index(g["start_date"])
    out = []
    for d in COURSE["days"]:
        idx = int(d["index"])
        window = await db.group_lesson_window(g["id"], idx)
        if not window or window[0] > now:
            continue
        kind = "hackathon" if d.get("hackathon") else "lesson"
        if await db.mentor_session_closed(mentor_id, g["id"], idx, kind) \
                and not await _needs_baseline(g["id"], idx):
            continue
        label = f"День {idx}" + (" · сегодня" if idx == today else "")
        out.append({**d, "_label": label})
    return out


async def _offer(message: Message, g, mentor_id: int) -> None:
    gid = g["id"]
    days = await _open_days(g, mentor_id)
    if days is None:
        days = COURSE["days"]          # без даты старта не знаем, что уже прошло
    if not days:
        await message.answer(f"Группа {g['name']}: все прошедшие дни у тебя заполнены 👍",
                             reply_markup=kb.pick_day(gid, []))  # остаётся кнопка финального опроса
        return
    await message.answer(
        f"Группа {g['name']}. За какой день заполняем?",
        reply_markup=kb.pick_day(gid, days),
    )


@router.message(Command("final"))
async def final_entry(message: Message, state: FSMContext) -> None:
    await state.clear()
    mentor = await _mentor_or_none(message.from_user.id, message)
    if not mentor:
        return
    groups = await db.mentor_groups(mentor["id"])
    if not groups:
        await message.answer("К тебе не привязана группа.")
        return
    await message.answer(
        "<b>Финальный замер</b> — те же пять осей, что и на старте.\n"
        "Бот покажет, что ты ставил в первый день, чтобы оценивать изменение, "
        "а не абсолют. По кому мало эпизодов — попросит добрать один момент.",
        reply_markup=kb.start_checklist(groups[0]["id"], 0, "final"),
    )


@router.callback_query(F.data.startswith("ck:later:"))
async def later(call: CallbackQuery) -> None:
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.message.answer("Ок, напомню позже. Захочешь раньше — /checklist.")
    await call.answer()


@router.callback_query(F.data.startswith("ck:skip:"))
async def skip(call: CallbackQuery) -> None:
    _, _, gid, day, kind = call.data.split(":")
    mentor = await db.mentor_by_tg(call.from_user.id)
    if not mentor:
        await call.answer("Сначала /start", show_alert=True)
        return
    await db.skip_session(mentor["id"], int(gid), int(day), kind)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.message.answer("Ок, по этой паре напоминать не буду. Если всё же вёл — /checklist.")
    await call.answer()


# ----------------------------------------------------------------- запуск

async def _needs_baseline(group_id: int, day_index: int) -> bool:
    """Стартовый замер идёт хвостом опроса первого дня, пока его никто в группе
    не закончил. В базе это по-прежнему отдельная сессия kind='baseline'."""
    return day_index == 1 and not await db.session_done(group_id, 1, "baseline")


@router.callback_query(F.data.startswith("ck:start:"))
async def start_survey(call: CallbackQuery, state: FSMContext) -> None:
    _, _, gid, day, kind = call.data.split(":")
    group_id, day_index = int(gid), int(day)
    mentor = await db.mentor_by_tg(call.from_user.id)
    if not mentor:
        await call.answer("Сначала /start", show_alert=True)
        return
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    # Урок дня 1 уже сдан, а замера нет — сразу к замеру, урок не переспрашиваем.
    if kind == "lesson" and await _needs_baseline(group_id, day_index) \
            and await db.mentor_session_closed(mentor["id"], group_id, day_index, "lesson"):
        kind = "baseline"
    await _begin(call.message, state, mentor["id"], group_id, day_index, kind)
    await call.answer()


async def _begin(message: Message, state: FSMContext, mentor_id: int,
                 group_id: int, day_index: int, kind: str) -> None:
    students = await db.students(group_id)
    if not students:
        await message.answer("В группе нет учеников — админ ещё не загрузил список.")
        return

    episodes = await db.episode_counts(group_id)
    spotlight = []
    if kind == "lesson":
        # Выбор по данным до этого дня — у второго ментора группы прожектор тот же.
        spotlight = flow.pick_spotlight(students, await db.episode_counts(group_id, day_index),
                                        await db.spotlight_counts(group_id, day_index))
    teams = sorted({s["team"] for s in students if s["team"]}) or ["без команды"]

    steps = flow.build_steps(kind, students, spotlight=spotlight,
                             teams=teams, episode_counts=episodes)

    session_id = await db.open_session(mentor_id, group_id, day_index, kind)
    answered = {
        (r["question_key"], r["student_id"])
        for r in await db.q("SELECT question_key, student_id FROM answers "
                            "WHERE session_id = ?", session_id)
    }
    steps = flow.drop_answered(steps, answered)

    if not steps:
        await db.finish_session(session_id)
        if kind == "lesson" and await _needs_baseline(group_id, day_index):
            await _begin(message, state, mentor_id, group_id, day_index, "baseline")
            return
        await message.answer("Тут уже всё заполнено. ✅")
        return

    await state.set_state(Survey.answering)
    await state.update_data(
        session_id=session_id, mentor_id=mentor_id, group_id=group_id,
        day_index=day_index, kind=kind,
        steps=steps, idx=0, selected=[], given={}, started_ts=time.time(),
        spotlight=[s["short_name"] or s["full_name"] for s in spotlight],
    )

    if kind == "baseline":
        await message.answer(
            "📋 <b>Стартовый замер</b> — последняя часть опроса первого дня, один раз за курс: "
            "интересы, что уже есть за плечами и пять осей по 0–10 по каждому ученику. "
            "Без него не будет блока «Было → Стало» в характеристиках.\n\nПрервать — /stop."
        )
        await _ask(message, state)
        return

    head = KIND_TITLES.get(kind, "Опрос")
    if kind == "lesson":
        head += f" · день {day_index} — {day_meta(day_index)['title']}"
    tail = ""
    if spotlight:
        tail = ("\n🔦 Прожектор сегодня на: <b>"
                + "</b> и <b>".join(s["short_name"] or s["full_name"] for s in spotlight)
                + "</b> — по ним пара вопросов подробнее.")
    if kind == "lesson" and await _needs_baseline(group_id, day_index):
        tail += "\nПосле урока — стартовый замер по каждому ученику, он один раз за курс."
    await message.answer(
        f"{head}\nПро большинство ничего спрашивать не буду — только про тех, "
        f"кого отметишь.{tail}\n\nПрервать — /stop."
    )
    await _ask(message, state)


@router.message(Command("stop"), Survey.answering)
@router.message(Command("stop"), Survey.editing)
async def stop_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Остановил. Ответы сохранены — продолжить через /checklist.")


@router.callback_query(F.data == "ck:stop", Survey.answering)
@router.callback_query(F.data == "ck:stop", Survey.editing)
async def stop_cb(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.message.answer("Остановил. Ответы сохранены — продолжить через /checklist.")
    await call.answer()


# ----------------------------------------------------------------- вопрос

async def _visible_students(step: dict, data: dict) -> list:
    """Список для мультивыбора. Кого уже отметили отсутствующим — не показываем."""
    students = await db.students(data["group_id"])
    excluded = set(data.get("given", {}).get(step["exclude"]) or []) if step["exclude"] else set()
    return [s for s in students if s["id"] not in excluded]


async def _ask(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    steps, idx = data["steps"], data["idx"]

    # пропускаем вопросы, чьё условие не выполнилось (например «что не пошло?»
    # спрашиваем только если урок был отмечен как тяжёлый)
    while idx < len(steps) and not flow.should_ask(steps[idx], data.get("given", {})):
        idx += 1
    if idx != data["idx"]:
        await state.update_data(idx=idx)
    if idx >= len(steps):
        await _finish(message, state)
        return

    step = steps[idx]
    body = f"<b>{step['text']}</b>"
    if step["hint"]:
        body += f"\n<i>{step['hint']}</i>"
    text = f"{flow.progress(steps, idx)}\n\n{body}"

    if step["type"] == "choice":
        await message.answer(text, reply_markup=kb.choice(step["options"], step["skippable"]))
    elif step["type"] == "scale10":
        prev = None
        if step.get("show_previous") and step.get("axis_code"):
            prev = await db.axis_value(step["student_id"], step["axis_code"], "baseline")
            if prev is not None:
                text += f"\n\n<i>На старте ты поставил <b>{prev}</b>. Что сейчас?</i>"
        await message.answer(text, reply_markup=kb.scale10(prev))
    elif step["type"] == "students_multi":
        await state.update_data(selected=[])
        await message.answer(text, reply_markup=kb.students_multi(
            await _visible_students(step, data), set(), step["empty_label"]))
    elif step["type"] == "tags":
        await state.update_data(selected=[])
        await message.answer(text, reply_markup=kb.tags_multi(step["tags"], set()))
    else:
        await message.answer(text, reply_markup=kb.text_answer(step["skippable"]))


async def _advance(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.update_data(idx=data["idx"] + 1)
    await _ask(message, state)


async def _save(state: FSMContext, step: dict, value: str | None,
                text: str | None, source: str,
                student_id_override: int | None = None) -> int:
    data = await state.get_data()
    return await db.save_answer(
        session_id=data["session_id"], group_id=data["group_id"],
        day_index=data["day_index"], question_key=step["key"],
        question_text=step["text"], maps_to=step["maps_to"],
        student_id=step["student_id"] if student_id_override is None else student_id_override,
        value=value, text=text, source=source,
    )


async def _remember(state: FSMContext, key: str, value) -> None:
    data = await state.get_data()
    given = dict(data.get("given") or {})
    given[key] = value
    await state.update_data(given=given)


async def _finish(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await db.finish_session(data["session_id"])
    group_id, kind = data["group_id"], data["kind"]

    elapsed = int(time.time() - float(data.get("started_ts") or time.time()))
    mins, secs = divmod(max(elapsed, 0), 60)
    took = f"{mins} мин {secs} сек" if mins else f"{secs} сек"

    # что собрали за эту сессию
    rows = await db.q(
        """SELECT question_key, student_id, text FROM answers
           WHERE session_id = ? AND text IS NOT NULL AND TRIM(text) <> ''""",
        data["session_id"],
    )
    episodes = sum(1 for r in rows if r["question_key"] in db.EPISODE_KEYS)
    absent = len(data.get("given", {}).get("absent") or [])
    nohw = len(data.get("given", {}).get("homework") or [])

    parts = [f"✅ Готово. Заняло {took}."]
    if kind == "lesson":
        bits = [f"эпизодов: {episodes}"]
        if absent:
            bits.append(f"отсутствовало: {absent}")
        if nohw:
            bits.append(f"не сдали: {nohw}")
        parts.append("Собрано — " + ", ".join(bits) + ".")

    # красный флаг: по кому за весь курс до сих пор пусто
    counts = await db.episode_counts(group_id)
    students = await db.students(group_id)
    empty = [s["short_name"] or s["full_name"] for s in students
             if counts.get(s["id"], 0) == 0]
    if empty and kind in ("lesson", "hackathon"):
        parts.append(
            f"\n⚠️ По {', '.join(empty)} за весь курс пока ноль эпизодов. "
            "На следующем уроке присмотрись — иначе в характеристике нечем "
            "наполнить «сильные стороны». Прожектор сам встанет на них."
        )

    if kind == "baseline":
        parts.append("\nСтартовый замер сохранён. Дальше — обычные опросы после уроков.")
    if kind == "final":
        parts.append("\nЗабрать материалы для характеристик — /export")

    await state.clear()
    if kind == "lesson" and data.get("mentor_id") \
            and await _needs_baseline(group_id, data["day_index"]):
        await message.answer(f"✅ Урок записан. Заняло {took}.")
        await _begin(message, state, data["mentor_id"], group_id, data["day_index"], "baseline")
        return
    await message.answer("\n".join(parts))


# ----------------------------------------------------------------- ответы

@router.callback_query(F.data.startswith("ck:opt:"), Survey.answering)
async def answer_choice(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    step = data["steps"][data["idx"]]
    value = call.data.split(":", 2)[2]
    label = next((o["label"] for o in step["options"] if str(o["value"]) == value), value)
    await _save(state, step, value, label, "button")
    await _remember(state, step["key"], value)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer(label)
    await _advance(call.message, state)


@router.callback_query(F.data.startswith("ck:s10:"), Survey.answering)
async def answer_scale10(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    step = data["steps"][data["idx"]]
    value = call.data.split(":")[2]
    await _save(state, step, value, f"{step.get('axis_label', '')}: {value}/10", "button")
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer(f"{value}/10")
    await _advance(call.message, state)


@router.callback_query(F.data == "ck:skip", Survey.answering)
async def answer_skip(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    step = data["steps"][data["idx"]]
    await _save(state, step, None, None, "skip")
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer("Пропущено")
    await _advance(call.message, state)


# --- мультивыбор учеников ---

@router.callback_query(F.data.startswith("ck:stu:"), Survey.answering)
async def toggle_student(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    step = data["steps"][data["idx"]]
    sid = int(call.data.split(":")[2])
    selected = set(data.get("selected") or [])
    selected.symmetric_difference_update({sid})
    await state.update_data(selected=sorted(selected))
    await call.message.edit_reply_markup(reply_markup=kb.students_multi(
        await _visible_students(step, data), selected, step["empty_label"]))
    await call.answer()


@router.callback_query(F.data.in_({"ck:stu_done", "ck:stu_none"}), Survey.answering)
async def finish_students(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    steps, idx = data["steps"], data["idx"]
    step = steps[idx]
    selected = [] if call.data == "ck:stu_none" else list(data.get("selected") or [])

    chosen = [await db.student(s) for s in selected]
    chosen = [c for c in chosen if c]
    names = [c["short_name"] or c["full_name"] for c in chosen]

    await _save(state, step, ",".join(map(str, selected)),
                ", ".join(names) or "никто", "button")
    # отметка на каждого — чтобы попала в его личные заметки
    for c in chosen:
        await db.save_answer(
            session_id=data["session_id"], group_id=data["group_id"],
            day_index=data["day_index"], question_key=step["key"] + "_mark",
            question_text=step["text"], maps_to=step["maps_to"],
            student_id=c["id"], value="1", text="да", source="button",
        )
    await _remember(state, step["key"], selected)

    # подвопросы разворачиваем только на отмеченных
    extra = flow.expand_for(step, chosen)
    if extra:
        steps = steps[:idx + 1] + extra + steps[idx + 1:]
        await state.update_data(steps=steps)

    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer(", ".join(names) or "никто")
    await _advance(call.message, state)


# --- мультивыбор тегов ---

@router.callback_query(F.data.startswith("ck:tag:"), Survey.answering)
async def toggle_tag(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    step = data["steps"][data["idx"]]
    code = call.data.split(":")[2]
    selected = set(data.get("selected") or [])
    selected.symmetric_difference_update({code})
    await state.update_data(selected=sorted(selected))
    await call.message.edit_reply_markup(
        reply_markup=kb.tags_multi(step["tags"], selected))
    await call.answer()


@router.callback_query(F.data == "ck:tag_done", Survey.answering)
async def finish_tags(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    step = data["steps"][data["idx"]]
    selected = list(data.get("selected") or [])
    labels = [t["label"] for t in step["tags"] if t["code"] in selected]

    # по строке на тег — так их потом можно считать и ранжировать
    for code, label in zip(selected, labels):
        await _save(state, step, code, label, "button")
    if not selected:
        await _save(state, step, None, None, "skip")

    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer(", ".join(labels) or "ничего")
    await _advance(call.message, state)


# --- свободный ответ: текст или голос ---

@router.message(Survey.answering, F.voice | F.audio)
async def answer_voice(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    step = data["steps"][data["idx"]]
    if step["type"] != "text":
        await message.answer("На этот вопрос ответь кнопкой выше.")
        return

    note = await message.answer("🎙 Расшифровываю…")
    voice = message.voice or message.audio
    path = Path(settings.media_dir) / f"{message.chat.id}_{message.message_id}.oga"
    try:
        await bot.download(voice.file_id, destination=str(path))
        roster = await db.students(data["group_id"])
        tr = await stt.transcribe(
            path, names=[s["short_name"] or s["full_name"] for s in roster])
    except stt.STTUnavailable as e:
        await note.edit_text(f"Не могу расшифровать голос: {e}\nНапиши текстом.")
        return
    except Exception:
        log.exception("Ошибка расшифровки")
        await note.edit_text("Расшифровка сорвалась. Напиши текстом, пожалуйста.")
        return
    finally:
        path.unlink(missing_ok=True)

    if not tr:
        await note.edit_text("В записи ничего не разобрал. Ещё раз или текстом.")
        return

    if _needs_confirm(tr, getattr(voice, "duration", None)):
        await state.update_data(pending_text=tr.text)
        await note.edit_text(
            f"🎙 <i>{tr.text}</i>\n\n⚠️ Распознал неуверенно — проверь. Сохранить?",
            reply_markup=kb.voice_confirm())
        return

    answer_id = await _save(state, step, None, tr.text, "voice")
    await note.edit_text(f"🎙 <i>{tr.text}</i>", reply_markup=kb.voice_saved(answer_id))
    await _advance(message, state)


@router.callback_query(F.data == "ck:vok", Survey.answering)
async def voice_confirm_save(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    text = data.get("pending_text")
    if not text:
        await call.answer("Нечего сохранять")
        return
    step = data["steps"][data["idx"]]
    answer_id = await _save(state, step, None, text, "voice")
    await state.update_data(pending_text=None)
    await call.message.edit_text(f"🎙 <i>{text}</i>",
                                 reply_markup=kb.voice_saved(answer_id))
    await call.answer("Сохранил")
    await _advance(call.message, state)


@router.callback_query(F.data == "ck:vredo", Survey.answering)
async def voice_redo(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(pending_text=None)
    try:
        await call.message.edit_text("🎙 <s>расшифровка отброшена</s>")
    except Exception:
        pass
    await call.answer("Давай заново")
    await _ask(call.message, state)


@router.message(Survey.answering, F.text)
async def answer_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    step = data["steps"][data["idx"]]
    text = message.text.strip()

    if text.startswith("/"):
        await message.answer("Идёт опрос. Чтобы выйти — /stop.")
        return

    if step["type"] == "scale10":
        if text.isdigit() and 0 <= int(text) <= 10:
            await _save(state, step, text, f"{step.get('axis_label','')}: {text}/10", "text")
            await _advance(message, state)
        else:
            await message.answer("Нужно число от 0 до 10 — кнопкой или цифрой.")
        return

    if step["type"] == "choice":
        match = next((o for o in step["options"]
                      if text.lower() in (str(o["value"]).lower(), o["label"].lower())), None)
        if match:
            await _save(state, step, str(match["value"]), match["label"], "text")
            await _remember(state, step["key"], match["value"])
            await _advance(message, state)
        else:
            await message.answer("Выбери вариант кнопкой выше.")
        return

    if step["type"] in ("students_multi", "tags"):
        await message.answer("Отметь кнопками и нажми «Готово».")
        return

    if text in {"-", "—", "пропустить", "скип"} and step["skippable"]:
        await _save(state, step, None, None, "skip")
        await _advance(message, state)
        return

    await _save(state, step, None, text, "text")
    await _advance(message, state)


# ----------------------------------------------------------------- правка

@router.callback_query(F.data.startswith("ck:fix:"))
async def fix_answer(call: CallbackQuery, state: FSMContext) -> None:
    """Переписать сохранённый ответ. Работает и во время опроса, и после —
    кнопка живёт под старым сообщением."""
    answer_id = int(call.data.split(":")[2])
    row = await db.answer(answer_id)
    if not row:
        await call.answer("Этот ответ уже не найти", show_alert=True)
        return
    resume = await state.get_state() == Survey.answering
    await state.update_data(editing_id=answer_id, editing_resume=resume)
    await state.set_state(Survey.editing)
    await call.answer()
    await call.message.answer(
        f"✏️ Переписываем ответ на вопрос:\n<i>{row['question_text']}</i>\n\n"
        "Пришли новый — текстом или голосовым.",
        reply_markup=kb.text_answer(skippable=False),
    )


@router.message(Survey.editing, F.voice | F.audio | F.text)
async def apply_fix(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    answer_id = data.get("editing_id")
    row = await db.answer(answer_id) if answer_id else None
    if not row:
        await state.set_state(Survey.answering)
        await message.answer("Не нашёл, что переписывать.")
        return

    if message.text:
        if message.text.strip().startswith("/"):
            await message.answer("Сейчас жду новый ответ. Отменить — /stop.")
            return
        text, source = message.text.strip(), "text"
    else:
        note = await message.answer("🎙 Расшифровываю…")
        voice = message.voice or message.audio
        path = Path(settings.media_dir) / f"{message.chat.id}_{message.message_id}.oga"
        try:
            await bot.download(voice.file_id, destination=str(path))
            roster = await db.students(row["group_id"])
            tr = await stt.transcribe(
                path, names=[s["short_name"] or s["full_name"] for s in roster])
        except Exception as e:  # noqa: BLE001
            log.exception("Не расшифровал правку")
            await note.edit_text(f"Не вышло расшифровать ({e}). Напиши текстом.")
            return
        finally:
            path.unlink(missing_ok=True)
        if not tr:
            await note.edit_text("Ничего не разобрал. Ещё раз или текстом.")
            return
        await note.delete()
        text, source = tr.text, "voice"

    await db.update_answer(answer_id, text, source)
    await state.update_data(editing_id=None)
    await message.answer(f"✏️ Заменил:\n<i>{text}</i>",
                         reply_markup=kb.voice_saved(answer_id))

    if data.get("editing_resume") and data.get("steps"):
        await state.set_state(Survey.answering)
        await _ask(message, state)
    else:
        await state.clear()
