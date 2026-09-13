"""Сборка шагов опроса из config/questions.yaml.

Схема из ТЗ: опрос идёт по исключениям. Большая часть вопросов вообще не
задаётся — они разворачиваются только на тех учеников, которых ментор отметил.
Поэтому список шагов не статичен: часть появляется прямо по ходу опроса
(см. expand_for), а часть отсекается условием (см. should_ask).
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

from app.config import QUESTIONS

TAGS: dict = QUESTIONS.get("tags") or {}
AXES: list[dict] = QUESTIONS.get("axes") or []
RUBRIC: list[dict] = QUESTIONS.get("rubric") or []


def tag_set(name: str) -> list[dict]:
    if name == "rubric":
        return RUBRIC
    return TAGS.get(name) or []


def _fmt(value: str | None, student: Any | None, team: str | None) -> str:
    if not value:
        return ""
    name = ""
    if student is not None:
        name = student["short_name"] or student["full_name"]
    return value.format(student=name, team=team or "")


def _step(q: dict, student: Any | None = None, team: str | None = None,
          extra: dict | None = None) -> dict:
    step = {
        "key": q["key"],
        "type": q.get("type", "text"),
        "text": _fmt(q.get("text"), student, team),
        "hint": _fmt(q.get("hint"), student, team),
        "maps_to": q.get("maps_to"),
        "options": q.get("options") or [],
        "tags": tag_set(q["tag_set"]) if q.get("tag_set") else [],
        "skippable": bool(q.get("skippable")),
        "skip_label": q.get("skip_label") or "Пропустить",
        "voice": bool(q.get("voice")),
        "empty_label": q.get("empty_label") or "— никто",
        "exclude": q.get("exclude"),
        "ask_if": q.get("ask_if"),
        "expand": q.get("expand") or [],
        "show_previous": bool(q.get("show_previous")),
        "student_id": student["id"] if student is not None else None,
        "student_name": (student["short_name"] or student["full_name"])
                        if student is not None else None,
        "team": team,
    }
    if extra:
        step.update(extra)
    return step


def _axes_steps(q: dict, student: Any) -> list[dict]:
    """axes_block разворачивается в пять отдельных шкал 0–10."""
    out = []
    for axis in AXES:
        out.append(_step(
            {
                "key": f"axis_{axis['code']}",
                "type": "scale10",
                "text": f"{{student}} · {axis['label']}\n{axis['question']}",
                "hint": q.get("hint") if axis is AXES[0] else None,
                "maps_to": "axes",
                "show_previous": q.get("show_previous"),
            },
            student,
            extra={"axis_code": axis["code"], "axis_label": axis["label"]},
        ))
    return out


# ----------------------------------------------------------------- прожектор

def pick_spotlight(students: list[Any], episode_counts: dict[int, int],
                   spotlight_counts: dict[int, int], per_lesson: int = 2) -> list[Any]:
    """Двое за урок, по кругу.

    Приоритет — у кого меньше эпизодов; при равенстве у того, кто реже был
    под прожектором. Так к концу курса не остаётся ученика, про которого
    нечего написать, — а это главный риск всей затеи.
    """
    ranked = sorted(
        students,
        key=lambda s: (episode_counts.get(s["id"], 0),
                       spotlight_counts.get(s["id"], 0),
                       s["full_name"]),
    )
    return ranked[:per_lesson]


# ----------------------------------------------------------------- сборка

def build_steps(kind: str, students: Iterable[Any], *,
                spotlight: list[Any] | None = None,
                teams: list[str] | None = None,
                episode_counts: dict[int, int] | None = None) -> list[dict]:
    students = list(students)
    spotlight = spotlight or []
    episode_counts = episode_counts or {}
    steps: list[dict] = []

    if kind == "lesson":
        for q in QUESTIONS.get("lesson") or []:
            if q.get("scope") == "spotlight":
                for st in spotlight:
                    steps.append(_step(q, st))
            else:
                steps.append(_step(q))
        return steps

    if kind == "baseline":
        for st in students:
            for q in QUESTIONS.get("baseline") or []:
                if q.get("type") == "axes_block":
                    steps.extend(_axes_steps(q, st))
                else:
                    steps.append(_step(q, st))
        return steps

    if kind == "final":
        for st in students:
            for q in QUESTIONS.get("final") or []:
                if q.get("type") == "axes_block":
                    steps.extend(_axes_steps(q, st))
                    continue
                few = q.get("ask_if_few_episodes")
                if few is not None and episode_counts.get(st["id"], 0) >= int(few):
                    continue          # эпизодов хватает — добор не нужен
                steps.append(_step(q, st))
        return steps

    if kind == "hackathon":
        for team in (teams or []):
            for q in QUESTIONS.get("hackathon_team") or []:
                steps.append(_step(q, None, team))
        for st in students:
            for q in QUESTIONS.get("hackathon_student") or []:
                steps.append(_step(q, st, st["team"]))
        return steps

    raise ValueError(f"неизвестный вид опроса: {kind}")


def expand_for(step: dict, students: list[Any]) -> list[dict]:
    """Подвопросы по каждому отмеченному ученику. Никого не отметили — пусто."""
    out: list[dict] = []
    for st in students:
        for q in step.get("expand") or []:
            out.append(_step(q, st))
    return out


def should_ask(step: dict, given: dict[str, Any]) -> bool:
    cond = step.get("ask_if")
    if not cond:
        return True
    return str(given.get(cond["key"])) == str(cond["value"])


def drop_answered(steps: list[dict], answered: set[tuple[str, Optional[int]]]) -> list[dict]:
    return [s for s in steps if (s["key"], s["student_id"]) not in answered]


def progress(steps: list[dict], idx: int) -> str:
    total, cur = len(steps), min(idx + 1, len(steps))
    step = steps[idx]
    if step["student_name"]:
        return f"👤 {step['student_name']}  ·  шаг {cur} из {total}"
    if step.get("team"):
        return f"🏁 команда {step['team']}  ·  шаг {cur} из {total}"
    return f"шаг {cur} из {total}"
