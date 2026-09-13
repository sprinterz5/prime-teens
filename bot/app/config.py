"""Загрузка настроек из .env и YAML-конфигов."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


def _ids(key: str) -> set[int]:
    raw = _env(key)
    return {int(x) for x in raw.replace(";", ",").split(",") if x.strip().isdigit()}


@dataclass(frozen=True)
class Settings:
    bot_token: str = field(default_factory=lambda: _env("BOT_TOKEN"))
    admin_ids: set[int] = field(default_factory=lambda: _ids("ADMIN_IDS"))
    tz_name: str = field(default_factory=lambda: _env("TZ", "Asia/Almaty"))

    # Детский бот — персональные ссылки для учеников ведут туда (свой бот, не этот).
    kids_bot_username: str = field(default_factory=lambda: _env("KIDS_BOT_USERNAME"))
    kids_bot_token: str = field(default_factory=lambda: _env("KIDS_BOT_TOKEN"))

    # Синхронизация с Google-таблицей: бот САМ забирает данные по расписанию
    # (integrations/sheets_sync.gs, опубликованный как Web App). Пустой URL —
    # ни /sync_sheet, ни ночной автозабор ничего не делают, просто молчат.
    sheets_sync_url: str = field(default_factory=lambda: _env("SHEETS_SYNC_URL"))
    sheets_sync_token: str = field(default_factory=lambda: _env("SHEETS_SYNC_TOKEN"))
    sheets_sync_hour: int = field(default_factory=lambda: int(_env("SHEETS_SYNC_HOUR", "3")))

    db_path: Path = field(default_factory=lambda: ROOT / _env("DB_PATH", "data/bot.sqlite3"))
    media_dir: Path = field(default_factory=lambda: ROOT / _env("MEDIA_DIR", "data/media"))
    out_dir: Path = field(default_factory=lambda: ROOT / _env("OUT_DIR", "data/out"))

    stt_provider: str = field(default_factory=lambda: _env("STT_PROVIDER", "faster_whisper"))
    whisper_model: str = field(default_factory=lambda: _env("WHISPER_MODEL", "small"))
    whisper_device: str = field(default_factory=lambda: _env("WHISPER_DEVICE", "cpu"))
    whisper_compute: str = field(default_factory=lambda: _env("WHISPER_COMPUTE_TYPE", "int8"))
    stt_base_url: str = field(default_factory=lambda: _env("STT_BASE_URL"))
    stt_api_key: str = field(default_factory=lambda: _env("STT_API_KEY"))
    stt_model: str = field(default_factory=lambda: _env("STT_MODEL", "whisper-1"))

    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "openai_compatible"))
    llm_base_url: str = field(default_factory=lambda: _env("LLM_BASE_URL"))
    llm_api_key: str = field(default_factory=lambda: _env("LLM_API_KEY"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "qwen3-8"))
    llm_temperature: float = field(default_factory=lambda: float(_env("LLM_TEMPERATURE", "0.4")))
    # qwen3-8 — reasoning-модель: часть бюджета уходит на скрытые размышления,
    # поэтому лимит заведомо больше, чем длина видимого ответа.
    llm_max_tokens: int = field(default_factory=lambda: int(_env("LLM_MAX_TOKENS", "10000")))

    # Автосборка характеристик — эксперимент. Основной путь — выгрузка материалов.
    experimental_characteristics: bool = field(
        default_factory=lambda: _env("EXPERIMENTAL_CHARACTERISTICS", "false").lower()
        in {"1", "true", "yes", "да"}
    )

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.tz_name)


settings = Settings()

COURSE: dict = yaml.safe_load((ROOT / "config" / "course.yaml").read_text(encoding="utf-8"))
QUESTIONS: dict = yaml.safe_load((ROOT / "config" / "questions.yaml").read_text(encoding="utf-8"))

# Заголовок дня нигде в course.yaml не хранится отдельно — он собирается из
# непустых блоков дня, чтобы тема не дублировалась в двух местах.
for _d in COURSE["days"]:
    _d.setdefault("title", " · ".join(
        (b.get("name") if isinstance(b, dict) else b)
        for b in _d.get("blocks", []) if b
    ))

DAYS_BY_INDEX: dict[int, dict] = {d["index"]: d for d in COURSE["days"]}

for _p in (settings.db_path.parent, settings.media_dir, settings.out_dir):
    _p.mkdir(parents=True, exist_ok=True)


def day_meta(index: int) -> dict:
    return DAYS_BY_INDEX.get(index, {"index": index, "title": f"День {index}", "blocks": []})
