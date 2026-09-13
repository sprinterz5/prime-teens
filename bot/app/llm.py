"""Сборка характеристики: заметки менторов -> структурированный JSON.

⚠️ Экспериментальная ветка. Основной путь — app/dossier.py: выгрузка заметок,
разложенных по разделам, чтобы характеристику написал человек. Здесь модель
пишет черновик, который в любом случае нужно перечитывать.

Провайдер — любой OpenAI-совместимый /v1/chat/completions. По умолчанию
Alem (https://llm.alem.ai/v1, модель qwen3-8). При LLM_PROVIDER=off черновик
собирается из сырых заметок вообще без модели.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.config import COURSE, settings

log = logging.getLogger(__name__)

# Что реально даёт курс — раздел 02 характеристики.
COURSE_SKILLS = [
    "Самопрезентация и рассказ о себе за 30 секунд",
    "Аргументация и дебаты, практика MUN",
    "Постановка исследовательского вопроса и гипотезы",
    "Работа с источниками и данными",
    "Запуск школьного клуба и волонтёрского проекта",
    "Планирование целей и приоритетов, работа с календарём",
    "Разбор кейса: от проблемы к решению, MVP",
    "Основы вайбкодинга и сборка первой версии продукта",
    "Олимпиадный трек и холодное письмо в организацию",
    "Сборка портфолио и CV",
    "Публичная защита проекта перед жюри",
]

SYSTEM = """Ты — методист образовательной программы PrimeTeens (Астана, летний
интенсив для 7–9 классов). Ты пишешь характеристику ученика по итогам курса.

Читатель — родитель. Тон: спокойный, уважительный, конкретный. Без канцелярита,
без психологических диагнозов, без превосходных степеней и без пустых похвал.

Железные правила:
1. Опирайся ТОЛЬКО на заметки менторов. Ничего не выдумывай: ни цифр, ни мест,
   ни названий, ни фактов, которых нет в заметках.
2. Если данных на раздел не хватает — напиши коротко и честно, обобщённо, но не
   придумывай событие. Пустая строка лучше выдуманной.
3. Каждая сильная сторона — с конкретным примером из заметок (что сделал, когда).
4. Зона роста формулируется как задача на будущее, а не как обвинение.
5. Пиши по-русски. Обращение к ученику — по имени, в третьем лице.
6. Ответ — ТОЛЬКО валидный JSON по схеме, без markdown-обёртки и комментариев.
"""

# Схема разбита на две части намеренно. qwen3-8 — reasoning-модель, и отключить
# размышления на llm.alem.ai нельзя (пробовали chat_template_kwargs,
# enable_thinking и /no_think — reasoning_content приходит всегда). Один запрос на
# всю схему упирался в лимит: finish_reason=length, JSON обрывался на середине.
# Три запроса поменьше проходят спокойно, и если один сорвётся — остальные уже
# собраны: документ придёт неполным, но не пустым.

SCHEMA_A = """Схема ответа (часть 1 из 2 — что было на курсе):
{
  "summary": "2-4 предложения: путь ученика за курс и главный результат",
  "learned": ["4-8 пунктов из списка освоенного на курсе, релевантных ученику"],
  "strengths": [
    {"title": "короткий заголовок сильной стороны",
     "detail": "1-2 предложения с конкретным примером из заметок"}
  ],
  "growth": {"before": "как было на первых занятиях",
             "after": "как стало к концу курса"},
  "growth_zone": {"title": "зона роста одной фразой",
                  "detail": "1-2 предложения, бережно и по делу",
                  "first_step": "конкретный первый шаг на ближайший месяц"},
  "done": {"attendance": "например: 7 из 8 занятий",
           "project": "кейс/команда/роль",
           "defense": "результат защиты",
           "portfolio": "состояние CV и портфолио",
           "goals": "цели на год"}
}
В "strengths" ровно 3 элемента."""

SCHEMA_B = """Схема ответа (часть 2 из 3 — портфолио и цель года):
{
  "portfolio": {"have": ["что уже есть после курса, 3-5 пунктов"],
                "todo": ["что предстоит за 10 месяцев, 4-6 пунктов"]},
  "year_goal": "одна главная цель года, одно предложение",
  "will_be_able": ["6-8 пунктов: что ученик сможет через 10 месяцев"]
}
Пункты должны расти из того, что видно в заметках, а не быть общими словами
про успех."""

SCHEMA_C = """Схема ответа (часть 3 из 3 — дорожная карта):
{
  "roadmap": [
    {"period": "Сентябрь — ноябрь", "title": "название этапа",
     "goal": "цель этапа одним предложением",
     "items": ["2-3 конкретных действия"]}
  ],
  "parallel": ["3-5 пунктов, что идёт параллельно все 10 месяцев"]
}
В "roadmap" ровно 4 квартала в таком порядке: сентябрь-ноябрь,
декабрь-февраль, март-апрель, май-июнь."""


def build_notes(student: Any, answers: list[Any], group_notes: list[Any]) -> str:
    """Собирает читаемый дайджест заметок для промпта."""
    days = {d["index"]: d for d in COURSE["days"]}
    lines: list[str] = [f"УЧЕНИК: {student['full_name']}"]
    if student["class_school"]:
        lines.append(f"КЛАСС/ШКОЛА: {student['class_school']}")
    if student["team"]:
        lines.append(f"КОМАНДА: {student['team']}")

    lines.append("\n=== ЗАМЕТКИ ПО УЧЕНИКУ ПО ДНЯМ ===")
    current_day = None
    for a in answers:
        if a["day_index"] != current_day:
            current_day = a["day_index"]
            if current_day == 0:
                lines.append("\n[Финальный опрос менторов]")
            else:
                meta = days.get(current_day, {})
                title = meta.get("title", "")
                lines.append(f"\n[День {current_day} — {title}]")
        text = (a["text"] or "").strip()
        if not text:
            continue
        lines.append(f"- {a['question_text'] or a['question_key']}: {text}")

    if group_notes:
        lines.append("\n=== КОНТЕКСТ ПО ГРУППЕ (общий, не про этого ученика) ===")
        for a in group_notes:
            text = (a["text"] or "").strip()
            if text:
                lines.append(f"- День {a['day_index']}: {text}")

    lines.append("\n=== ЧТО ДАЁТ КУРС (для раздела «Что освоено») ===")
    lines.extend(f"- {s}" for s in COURSE_SKILLS)
    return "\n".join(lines)


async def generate(student: Any, answers: list[Any], group_notes: list[Any]) -> dict:
    notes = build_notes(student, answers, group_notes)
    if settings.llm_provider == "off":
        return _fallback(student, notes)

    data: dict = {}
    errors: list[str] = []
    for label, schema in (("часть 1", SCHEMA_A), ("часть 2", SCHEMA_B),
                          ("часть 3", SCHEMA_C)):
        try:
            data.update(_parse_json(await _chat(notes, schema)))
        except Exception as e:  # noqa: BLE001 — один ученик не должен ронять всю пачку
            log.exception("LLM: %s не собралась для %s", label, student["full_name"])
            errors.append(f"{label}: {e or type(e).__name__}")

    if not data:
        out = _fallback(student, notes)
        out["_error"] = "; ".join(errors)
        return out
    if errors:
        # часть разделов собралась — отдаём что есть, шаблон пропустит пустые
        data["_error"] = "; ".join(errors)
        data.setdefault("raw_notes", notes)
    return data


async def _chat(notes: str, schema: str) -> str:
    if not settings.llm_base_url:
        raise RuntimeError("LLM_BASE_URL не задан")
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    payload = {
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"{schema}\n\n=== ИСХОДНЫЕ ЗАМЕТКИ ===\n{notes}"},
        ],
        # qwen3-8 на llm.alem.ai response_format держит — проверено.
        "response_format": {"type": "json_object"},
        # Это reasoning-модель: заметная часть бюджета уходит на скрытые
        # размышления (на односложный ответ ушло ~250 токенов), поэтому лимит
        # ставим с запасом, иначе документ обрежется на середине JSON.
        "max_tokens": settings.llm_max_tokens,
    }
    # Длинные генерации иногда обрываются на сети — один ретрай дешевле,
    # чем потерянный раздел документа.
    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            break
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            last_err = e
            log.warning("LLM: попытка %s не удалась (%s)", attempt, type(e).__name__)
    else:
        raise RuntimeError(f"сеть/эндпоинт: {last_err or 'нет ответа'}")

    choice = resp.json()["choices"][0]
    finish = choice.get("finish_reason")
    # При обрыве по лимиту content приходит либо обрезанным, либо вовсе null —
    # весь бюджет ушёл в reasoning_content. Это не «модель глупая», это лимит.
    content = choice.get("message", {}).get("content") or ""
    if finish == "length" or not content.strip():
        raise RuntimeError(
            f"ответ не поместился в лимит (finish_reason={finish}, "
            f"LLM_MAX_TOKENS={settings.llm_max_tokens}). "
            "Модель тратит часть бюджета на скрытые размышления — подними лимит."
        )
    return content


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    # Qwen любит <think>…</think> и ```json-обёртки — снимаем и то и другое.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


def _fallback(student: Any, notes: str) -> dict:
    """Без LLM: документ-черновик с сырыми заметками, чтобы ментор дописал руками."""
    return {
        "summary": f"Черновик: LLM отключён. Ниже — сырые заметки менторов по "
                   f"ученику {student['full_name']}. Отредактируйте вручную.",
        "learned": COURSE_SKILLS[:6],
        "strengths": [{"title": "Заполнить вручную", "detail": ""}],
        "growth": {"before": "", "after": ""},
        "growth_zone": {"title": "", "detail": "", "first_step": ""},
        "done": {},
        "portfolio": {"have": [], "todo": []},
        "year_goal": "",
        "will_be_able": [],
        "roadmap": [],
        "parallel": [],
        "raw_notes": notes,
    }
