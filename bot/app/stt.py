"""Распознавание голосовых.

Два провайдера:
  faster_whisper    — локально. Модель грузится один раз, лениво, при первом
                      голосовом. Само распознавание уводится в отдельный поток,
                      чтобы не блокировать event loop бота.
  openai_compatible — POST /v1/audio/transcriptions (Alem, OpenAI, любой прокси).

Про Alem: эндпоинт /v1/audio/transcriptions на llm.alem.ai живой, но ключ
выдаётся под конкретные модели. Ключ от qwen3-8 к нему не пускает —
отвечает "key can only access models=['qwen3-8']". Чтобы распознавать голос
через Alem, нужен отдельный ключ с доступом к модели Speech-to-text
(в каталоге есть обычная и казахская), и его имя в STT_MODEL.

Сам qwen3-8 — текстовая модель, звук она не принимает: её дело — сборка
черновика характеристики (app/llm.py), а не транскрибация.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.config import COURSE, settings

log = logging.getLogger(__name__)

_model = None
_model_lock = asyncio.Lock()


class STTUnavailable(RuntimeError):
    pass


def build_hint(names: list[str] | None = None) -> str:
    """Подсказка словаря для Whisper.

    Без неё модель калечит имена и термины: «Алия» превращается в «Одя и»,
    «Аружан отвлекалась» — в «оружие отвлекалось», MUN — в «МУН». Whisper смещает
    распознавание в сторону слов из initial_prompt, а состав группы бот и так
    знает — грех не подсказать.

    Порядок важен: faster-whisper обрезает промпт до последних ~224 токенов,
    поэтому имена идут в КОНЕЦ — их срезать нельзя, а хвост словаря переживём.
    Текст должен читаться как обычная фраза, а не как список через запятую.
    """
    parts = ["Заметка ментора курса PrimeTeens после занятия."]
    glossary = COURSE.get("stt_vocabulary") or []
    if glossary:
        parts.append("Термины курса: " + ", ".join(glossary) + ".")
    if names:
        parts.append("Имена учеников: " + ", ".join(names) + ".")
    return " ".join(parts)


# Кириллические буквы, неотличимые на вид от латинских. Whisper, распознавая
# «MUN», регулярно выдаёт «МUN» — кириллическая М плюс латинские UN.
_HOMOGLYPHS = str.maketrans("АВЕКМНОРСТУХаеорсух", "ABEKMHOPCTYXaeopcyx")
_MIXED = re.compile(r"\b(?=\w*[А-Яа-яЁё])(?=\w*[A-Za-z])\w+\b")


def normalize_terms(text: str) -> str:
    """Чинит термины, склеенные из кириллицы и латиницы.

    Трогаем только слова, где намешаны оба алфавита, и только если после замены
    похожих букв получился термин из словаря курса. Обычные слова так задеть
    нельзя — в них не бывает смеси алфавитов.
    """
    terms = {t.lower(): t for t in (COURSE.get("stt_vocabulary") or [])
             if t.isascii()}
    if not terms:
        return text

    def fix(m: re.Match[str]) -> str:
        word = m.group(0)
        latin = word.translate(_HOMOGLYPHS)
        return terms.get(latin.lower(), word)

    return _MIXED.sub(fix, text)


@dataclass
class Transcript:
    """Расшифровка вместе с оценкой уверенности модели.

    confidence — средний avg_logprob по сегментам: 0 — идеально, чем меньше,
    тем хуже. У удалённого провайдера его нет, тогда None и считаем уверенным.
    """
    text: str
    confidence: float | None = None

    @property
    def low(self) -> bool:
        if self.confidence is None:
            return False
        threshold = float((COURSE.get("voice") or {}).get("low_confidence", -0.6))
        return self.confidence < threshold

    def __bool__(self) -> bool:
        return bool(self.text.strip())


async def transcribe(path: Path, language: str = "ru",
                     names: list[str] | None = None) -> Transcript:
    provider = settings.stt_provider
    hint = build_hint(names)
    if provider == "off":
        raise STTUnavailable("Распознавание голоса отключено (STT_PROVIDER=off)")
    if provider == "faster_whisper":
        tr = await _faster_whisper(path, language, hint)
    elif provider == "openai_compatible":
        tr = await _remote(path, language, hint)
    else:
        raise STTUnavailable(f"Неизвестный STT_PROVIDER: {provider}")
    return Transcript(normalize_terms(tr.text), tr.confidence)


async def _load_model():
    global _model
    async with _model_lock:
        if _model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise STTUnavailable(
                    "faster-whisper не установлен. "
                    "Либо `pip install faster-whisper`, либо STT_PROVIDER=openai_compatible."
                ) from e
            log.info("Загружаю Whisper (%s, %s)…", settings.whisper_model, settings.whisper_device)
            _model = await asyncio.to_thread(
                WhisperModel,
                settings.whisper_model,
                device=settings.whisper_device,
                compute_type=settings.whisper_compute,
            )
    return _model


async def _faster_whisper(path: Path, language: str, hint: str = "") -> Transcript:
    model = await _load_model()

    def _run() -> Transcript:
        segments, _info = model.transcribe(
            str(path),
            language=language,
            vad_filter=True,
            beam_size=1,          # ментор диктует заметку, а не читает лекцию
            condition_on_previous_text=False,
            initial_prompt=hint or None,
        )
        parts, logprobs = [], []
        for s in segments:                      # генератор: считаем на лету
            parts.append(s.text.strip())
            if s.avg_logprob is not None:
                logprobs.append(s.avg_logprob)
        conf = sum(logprobs) / len(logprobs) if logprobs else None
        return Transcript(" ".join(parts).strip(), conf)

    return await asyncio.to_thread(_run)


async def _remote(path: Path, language: str, hint: str = "") -> Transcript:
    if not settings.stt_base_url:
        raise STTUnavailable("STT_BASE_URL не задан")
    url = settings.stt_base_url.rstrip("/") + "/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.stt_api_key}"} if settings.stt_api_key else {}
    data = {"model": settings.stt_model, "language": language}
    if hint:
        data["prompt"] = hint  # OpenAI-совместимое поле подсказки словаря
    async with httpx.AsyncClient(timeout=180) as client:
        with path.open("rb") as fh:
            files = {"file": (path.name, fh, "audio/ogg")}
            resp = await client.post(url, headers=headers, data=data, files=files)
    resp.raise_for_status()
    payload = resp.json()
    return Transcript((payload.get("text") or "").strip())
