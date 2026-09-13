"""Досье ученика — все заметки за курс, разложенные по разделам характеристики.

Никакой генерации: только сбор, группировка и подсчёты. На выходе человек
получает материал, из которого характеристика пишется руками за 10 минут,
потому что всё уже лежит под нужными заголовками и с датами.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import zipfile
from pathlib import Path
from typing import Any

from app import db, flow
from app.config import COURSE, DAYS_BY_INDEX, settings
from app.render import _env, _slug

# maps_to из questions.yaml -> (заголовок в досье, куда идёт в характеристике)
SECTIONS: dict[str, tuple[str, str]] = {
    "strengths":               ("Сильные стороны", "раздел 03 «Сильные стороны»"),
    "growth":                  ("Было → стало", "раздел 04 «Заметный рост»"),
    "growth_zones":            ("Зоны роста", "раздел 05 «Зоны роста»"),
    "project":                 ("Проект, команда, роль", "раздел 06 «Что сделано за курс»"),
    "project.role":            ("Роль в команде хакатона", "раздел 06"),
    "project.result":          ("Результат защиты", "раздел 06"),
    "portfolio.cv":            ("CV и портфолио", "раздел 07 «Портфолио сейчас»"),
    "goals":                   ("Цели на год", "разделы 06 и 08"),
    "roadmap":                 ("Куда двигаться дальше", "разделы 08–10, дорожная карта"),
    "skills.public_speaking":  ("Публичные выступления, MUN, дебаты", "разделы 02 и 03"),
    "skills.research":         ("Исследовательская работа", "разделы 02 и 03"),
    "skills.initiative":       ("Инициатива, клуб, волонтёрство", "разделы 03 и 05"),
    "observations":            ("Наблюдения по дням", "разделы 01, 03, 04"),
    "meta.class_school":       ("Класс и школа", "шапка документа"),
}

# Порядок вывода: сначала то, что прямо ложится в разделы, потом сырые наблюдения
SECTION_ORDER = [
    "strengths", "growth", "growth_zones", "roadmap", "goals",
    "project", "project.role", "project.result", "portfolio.cv",
    "skills.public_speaking", "skills.research", "skills.initiative",
    "meta.class_school",
]

def _times(n: int) -> str:
    """1 раз, 2 раза, 5 раз."""
    if 11 <= n % 100 <= 14:
        return f"{n} раз"
    return f"{n} раз" + {1: "", 2: "а", 3: "а", 4: "а"}.get(n % 10, "")


def _day_title(day_index: int) -> str:
    if day_index == 0:
        return "Финальный опрос"
    d = DAYS_BY_INDEX.get(day_index)
    return f"День {day_index} · {d['title']}" if d else f"День {day_index}"


async def build(student: Any) -> dict:
    """Собирает досье одного ученика."""
    answers = await db.student_answers(student["id"])
    group = await db.group(student["group_id"])
    sid = student["id"]

    missed_days: list[int] = []
    nohw_days: list[int] = []
    standout_days: list[int] = []
    struggled_days: list[int] = []
    episodes: list[dict] = []
    pos_tags: dict[str, int] = {}
    neg_tags: dict[str, int] = {}
    by_day: dict[int, list[dict]] = {}
    by_section: dict[str, list[dict]] = {}

    for a in answers:
        day, key, text = a["day_index"], a["question_key"], (a["text"] or "").strip()

        if key == "absent_mark":
            missed_days.append(day); continue
        if key == "homework_mark":
            nohw_days.append(day); continue
        if key == "standout_mark":
            standout_days.append(day); continue
        if key == "struggled_mark":
            struggled_days.append(day); continue
        if key.startswith("axis_"):
            continue                       # оси собираются отдельно, ниже
        if key == "standout_tags" and a["value"]:
            pos_tags[a["value"]] = pos_tags.get(a["value"], 0) + 1
            continue
        if key == "struggled_tags" and a["value"]:
            neg_tags[a["value"]] = neg_tags.get(a["value"], 0) + 1
            continue
        if not text or a["source"] == "skip":
            continue

        item = {
            "day": day,
            "day_title": _day_title(day),
            "question": a["question_text"] or key,
            "text": text,
            "source": a["source"],
        }
        if key in db.EPISODE_KEYS:
            episodes.append(item)
        if day == 0 or (a["maps_to"] or "") in SECTION_ORDER:
            by_section.setdefault(a["maps_to"] or "observations", []).append(item)
        else:
            by_day.setdefault(day, []).append(item)

    # --- пять осей: старт против финала ---
    axes = []
    for axis in flow.AXES:
        before = await db.axis_value(sid, axis["code"], "baseline")
        after = await db.axis_value(sid, axis["code"], "final")
        axes.append({
            "code": axis["code"], "label": axis["label"],
            "before": before, "after": after,
            "delta": (after - before) if (before is not None and after is not None) else None,
        })

    # --- теги словами ---
    pos_labels = {t["code"]: t["label"] for t in flow.tag_set("positive")}
    neg_labels = {t["code"]: t["label"] for t in flow.tag_set("negative")}
    positive = sorted(((pos_labels.get(c, c), n) for c, n in pos_tags.items()),
                      key=lambda x: -x[1])
    negative = sorted(((neg_labels.get(c, c), n) for c, n in neg_tags.items()),
                      key=lambda x: -x[1])

    # Правило ТЗ: зона роста — не низкий балл, а ОТСУТСТВИЕ проявлений.
    # Ни разу не отмечен «Говорил вслух» — публичная речь и есть зона роста,
    # независимо от оценок. А нулевой прирост при высоком старте — это
    # стабильно сильная сторона, и путать одно с другим нельзя.
    never_shown = [t["label"] for t in flow.tag_set("positive")
                   if t["code"] not in pos_tags]
    stable_strong = [a["label"] for a in axes
                     if a["delta"] == 0 and (a["before"] or 0) >= 7]

    lessons_total = len([d for d in COURSE["days"]
                         if d.get("post_lesson_checklist") is not False])

    return {
        "student": {
            "id": sid,
            "full_name": student["full_name"],
            "short_name": student["short_name"] or student["full_name"],
            "class_school": student["class_school"] or "",
            "team": student["team"] or "",
            "group": group["name"] if group else "",
        },
        "attendance": {
            "missed": sorted(set(missed_days)),
            "total": lessons_total,
            "present": lessons_total - len(set(missed_days)),
            "nohw": sorted(set(nohw_days)),
        },
        "axes": axes,
        "tags": {"positive": positive, "negative": negative},
        "episodes": sorted(episodes, key=lambda e: e["day"]),
        "insight": {"never_shown": never_shown, "stable_strong": stable_strong},
        "marks": {
            "standout_days": sorted(standout_days),
            "struggled_days": sorted(struggled_days),
        },
        "sections": [
            {
                "key": k,
                "title": SECTIONS.get(k, (k, ""))[0],
                "goes_to": SECTIONS.get(k, (k, ""))[1],
                "items": by_section[k],
            }
            for k in SECTION_ORDER if k in by_section
        ] + [
            {"key": k, "title": SECTIONS.get(k, (k, ""))[0],
             "goes_to": SECTIONS.get(k, (k, ""))[1], "items": v}
            for k, v in by_section.items() if k not in SECTION_ORDER
        ],
        "by_day": [{"day": d, "day_title": _day_title(d), "items": by_day[d]}
                   for d in sorted(by_day)],
        "counts": {
            "notes": sum(len(v) for v in by_day.values())
                     + sum(len(v) for v in by_section.values()),
            "episodes": len(episodes),
            "final_filled": any(a["after"] is not None for a in axes),
        },
    }


# --------------------------------------------------------------- markdown

def to_markdown(d: dict) -> str:
    s, out = d["student"], []
    out.append(f"# {s['full_name']}")
    meta = " · ".join(filter(None, [s["class_school"], s["group"],
                                    f"команда {s['team']}" if s["team"] else ""]))
    if meta:
        out.append(meta)

    att = d["attendance"]
    out.append(f"\n## Посещаемость\n\n**{att['present']} из {att['total']}**")
    if att["missed"]:
        out.append(f"Пропустил: дни {', '.join(map(str, att['missed']))}")
    if att["nohw"]:
        out.append(f"Не сдал задание: дни {', '.join(map(str, att['nohw']))}")

    axes = [a for a in d["axes"] if a["before"] is not None or a["after"] is not None]
    if axes:
        out.append("\n## Было → стало\n\n*→ раздел 04 «Заметный рост»*\n")
        out.append("| Ось | Старт | Финал | Δ |")
        out.append("|---|---|---|---|")
        for a in axes:
            b = a["before"] if a["before"] is not None else "—"
            f = a["after"] if a["after"] is not None else "—"
            dl = f"{a['delta']:+d}" if a["delta"] is not None else "—"
            out.append(f"| {a['label']} | {b} | {f} | {dl} |")

    epi = d["episodes"]
    out.append(f"\n## Эпизоды ({len(epi)})\n\n"
               "*→ конкретные примеры для разделов 01, 03, 04*\n")
    if epi:
        for e in epi:
            tag = " 🎙" if e["source"] == "voice" else ""
            out.append(f"- {e['text']}{tag} [{e['day_title']}]")
    else:
        out.append("**Эпизодов нет.** Писать сильные стороны не из чего.")

    tags = d["tags"]
    if tags["positive"] or tags["negative"]:
        out.append("\n## Теги менторов\n")
        if tags["positive"]:
            out.append("Сильное: " + " · ".join(f"{l} ×{n}" for l, n in tags["positive"]))
        if tags["negative"]:
            out.append("Мешало: " + " · ".join(f"{l} ×{n}" for l, n in tags["negative"]))

    ins = d["insight"]
    if ins["never_shown"] or ins["stable_strong"]:
        out.append("\n## Подсказки для зон роста\n")
        if ins["never_shown"]:
            out.append("Ни разу не отмечено за курс — это и есть зоны роста, "
                       "независимо от баллов:")
            out.extend(f"- {l}" for l in ins["never_shown"])
        if ins["stable_strong"]:
            out.append("\nНулевой прирост при высоком старте — это **стабильно "
                       "сильная сторона**, а не проблема: "
                       + ", ".join(ins["stable_strong"]))

    marks = d["marks"]
    if marks["standout_days"] or marks["struggled_days"]:
        out.append("\n## Отметки по урокам\n")
        if marks["standout_days"]:
            out.append(f"- Отличился: {_times(len(marks['standout_days']))} "
                       f"(дни {', '.join(map(str, marks['standout_days']))})")
        if marks["struggled_days"]:
            out.append(f"- Не шло: {_times(len(marks['struggled_days']))} "
                       f"(дни {', '.join(map(str, marks['struggled_days']))})")

    if d["sections"]:
        out.append("\n## Материал по разделам характеристики")
        for sec in d["sections"]:
            out.append(f"\n### {sec['title']}")
            if sec["goes_to"]:
                out.append(f"*→ {sec['goes_to']}*\n")
            for it in sec["items"]:
                tag = " 🎙" if it["source"] == "voice" else ""
                where = "" if it["day"] == 0 else f" [день {it['day']}]"
                out.append(f"- {it['text']}{tag}{where}")

    if d["by_day"]:
        out.append("\n## Наблюдения по дням")
        for day in d["by_day"]:
            out.append(f"\n### {day['day_title']}")
            for it in day["items"]:
                tag = " 🎙" if it["source"] == "voice" else ""
                out.append(f"- {it['text']}{tag}")

    out.append(f"\n---\n\nЗаметок всего: {d['counts']['notes']}. "
               f"Финальный опрос: {'заполнен' if d['counts']['final_filled'] else 'НЕ заполнен'}.")
    return "\n".join(out)


# --------------------------------------------------------------- csv

def group_csv(dossiers: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    axes = [a["label"] for a in flow.AXES]
    head = ["Ученик", "Класс/школа", "Команда", "Посещаемость", "Пропуски (дни)",
            "Не сдал (дни)", "Эпизодов", "Отличился (раз)", "Не шло (раз)"]
    for label in axes:
        head += [f"{label}: старт", f"{label}: финал", f"{label}: Δ"]
    head += ["Сильные теги", "Проблемные теги", "Ни разу не проявлено"]
    w.writerow(head)

    for d in dossiers:
        s, att, m = d["student"], d["attendance"], d["marks"]
        row = [
            s["full_name"], s["class_school"], s["team"],
            f"{att['present']}/{att['total']}",
            " ".join(map(str, att["missed"])), " ".join(map(str, att["nohw"])),
            d["counts"]["episodes"],
            len(m["standout_days"]), len(m["struggled_days"]),
        ]
        for a in d["axes"]:
            row += [
                a["before"] if a["before"] is not None else "",
                a["after"] if a["after"] is not None else "",
                f"{a['delta']:+d}" if a["delta"] is not None else "",
            ]
        row += [
            " ".join(f"{l}×{n}" for l, n in d["tags"]["positive"]),
            " ".join(f"{l}×{n}" for l, n in d["tags"]["negative"]),
            " ".join(d["insight"]["never_shown"]),
        ]
        w.writerow(row)
    return buf.getvalue()


# --------------------------------------------------------------- сборка пакета

async def export_group(group_id: int) -> tuple[Path, Path, dict]:
    """Готовит ZIP с материалами и общий HTML. Возвращает (zip, html, статистика)."""
    group = await db.group(group_id)
    students = await db.students(group_id)
    group_notes = await db.group_answers(group_id)

    dossiers = [await build(st) for st in students]
    stamp = dt.datetime.now(settings.tz).strftime("%Y%m%d_%H%M")
    base = _slug(group["name"])

    notes_by_day: dict[int, list[dict]] = {}
    for a in group_notes:
        text = (a["text"] or "").strip()
        if text and a["source"] != "skip":
            notes_by_day.setdefault(a["day_index"], []).append(
                {"question": a["question_text"] or a["question_key"], "text": text}
            )
    group_log = [{"day": d, "day_title": _day_title(d), "items": notes_by_day[d]}
                 for d in sorted(notes_by_day)]

    html = _env.get_template("dossier.html.j2").render(
        group=group, dossiers=dossiers, group_log=group_log,
        generated_at=dt.datetime.now(settings.tz).strftime("%d.%m.%Y %H:%M"),
        sections_help=SECTIONS,
    )
    html_path = settings.out_dir / f"materialy_{base}_{stamp}.html"
    html_path.write_text(html, encoding="utf-8")

    zip_path = settings.out_dir / f"materialy_{base}_{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{base}/svodnaya_tablica.csv", group_csv(dossiers))
        z.writestr(f"{base}/vse_ucheniki.html", html)
        for d in dossiers:
            name = _slug(d["student"]["full_name"])
            z.writestr(f"{base}/ucheniki/{name}.md", to_markdown(d))
        z.writestr(f"{base}/syrye_dannye.json",
                   json.dumps({"group": group["name"], "students": dossiers,
                               "group_log": group_log},
                              ensure_ascii=False, indent=2))
        z.writestr(f"{base}/КАК_ПОЛЬЗОВАТЬСЯ.txt", HOWTO)

    stats = {
        "students": len(dossiers),
        "notes": sum(d["counts"]["notes"] for d in dossiers),
        "final_done": sum(1 for d in dossiers if d["counts"]["final_filled"]),
        "empty": [d["student"]["full_name"] for d in dossiers if d["counts"]["notes"] == 0],
    }
    return zip_path, html_path, stats


HOWTO = """МАТЕРИАЛЫ ДЛЯ ХАРАКТЕРИСТИК — что где лежит

vse_ucheniki.html    Открыть в браузере. Всё по всем ученикам, разложено по
                     разделам характеристики. Печать -> Сохранить как PDF.

ucheniki/*.md        По одному файлу на ученика, текстом. Удобно копировать
                     куски прямо в документ характеристики.

svodnaya_tablica.csv Таблица по группе: посещаемость, включённость по дням и
                     её динамика, сколько раз отмечен как вытягивающий или
                     выпадающий. Открывается в Excel (разделитель — точка с
                     запятой, кодировка UTF-8).

syrye_dannye.json    Всё то же самое машиночитаемо — если захочется свести
                     самому или прогнать через модель.

КАК ЭТИМ ПОЛЬЗОВАТЬСЯ

В каждом досье блок «Материал по разделам характеристики»: под каждым
заголовком написано, в какой раздел документа он идёт. Сильные стороны — в
раздел 03, «было -> стало» — в 04, зона роста — в 05 и так далее.

Ниже блок «Наблюдения по дням» — это сырые заметки менторов с занятий. Из них
берутся конкретные примеры: без примера сильная сторона превращается в
«молодец», а такое родителю ничего не говорит.

Цифры (посещаемость, включённость, отметки) — не для документа напрямую, а
чтобы проверить себя: если пишете про рост, а включённость весь курс ровная,
значит рост был в чём-то другом.
"""
