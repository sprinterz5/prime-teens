"""Рендер характеристики в HTML (и в PDF, если стоит weasyprint)."""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import ROOT, settings

_env = Environment(
    loader=FileSystemLoader(ROOT / "templates"),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _slug(name: str) -> str:
    translit = str.maketrans(
        "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
        "abvgdeejzijklmnoprstufhccss_y_eua",
    )
    s = name.lower().translate(translit)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "student"


def render_html(student: Any, data: dict, mentors: str = "",
                course_name: str = "PrimeTeens · летний интенсив",
                duration: str = "8 занятий, 2 недели + финальный хакатон") -> Path:
    tpl = _env.get_template("characteristic.html.j2")
    html = tpl.render(
        student=student,
        data=data,
        mentors=mentors,
        course_name=course_name,
        duration=duration,
        generated_at=dt.datetime.now(settings.tz).strftime("%d.%m.%Y"),
    )
    stamp = dt.datetime.now(settings.tz).strftime("%Y%m%d_%H%M")
    path = settings.out_dir / f"harakteristika_{_slug(student['full_name'])}_{stamp}.html"
    path.write_text(html, encoding="utf-8")
    return path


def try_pdf(html_path: Path) -> Optional[Path]:
    """PDF только если установлен weasyprint. Иначе None — отдаём HTML."""
    try:
        from weasyprint import HTML  # type: ignore
    except Exception:
        return None
    pdf_path = html_path.with_suffix(".pdf")
    try:
        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        return pdf_path
    except Exception:
        return None
