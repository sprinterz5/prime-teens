"""Проверка распознавания голоса.

    python -m tools.test_stt файл.oga [ещё файлы...] [--names=Алия,Данияр]

С --names прогоняет каждый файл дважды — без словаря и с ним, чтобы было видно,
что подсказка реально меняет.

Гоняет файл через тот же код, что и бот (app/stt.py), с теми же настройками из
.env. Печатает текст, время распознавания и скорость относительно длительности
записи — по ней понятно, потянет ли машина живой поток голосовых от менторов.

Где взять .oga: запиши себе голосовое в Telegram, нажми на нём «Сохранить как».
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import stt  # noqa: E402
from app.config import settings  # noqa: E402


def duration(path: Path) -> float | None:
    try:
        import av
    except ImportError:
        return None
    try:
        with av.open(str(path)) as c:
            return float(c.duration) / 1_000_000 if c.duration else None
    except Exception:
        return None


async def run_one(path: Path, names: list[str] | None, label: str) -> None:
    dur = duration(path)
    t0 = time.perf_counter()
    try:
        tr = await stt.transcribe(path, names=names)
    except Exception as e:  # noqa: BLE001
        print(f"  {label}: ❌ {type(e).__name__}: {e}")
        return
    took = time.perf_counter() - t0
    speed = f", ×{dur / took:.1f} реального времени" if dur and took else ""
    conf = ""
    if tr.confidence is not None:
        conf = (f", уверенность {tr.confidence:.2f}"
                + (" ⚠️ спросит подтверждение" if tr.low else ""))
    print(f"  {label}  ⏱ {took:.1f} с{speed}{conf}")
    print(f"     {tr.text or '(пусто)'}")


async def main(paths: list[str], names: list[str] | None) -> None:
    print(f"провайдер: {settings.stt_provider}")
    if settings.stt_provider == "faster_whisper":
        print(f"модель: {settings.whisper_model} · {settings.whisper_device} · "
              f"{settings.whisper_compute}")
    if names:
        print(f"подсказка: {len(names)} имён + "
              f"{len(stt.COURSE.get('stt_vocabulary') or [])} терминов")
    print()

    for raw in paths:
        path = Path(raw)
        if not path.exists():
            print(f"❌ нет файла: {path}")
            continue
        dur = duration(path)
        print(f"▸ {path.name}  ({path.stat().st_size / 1024:.0f} КБ"
              + (f", {dur:.1f} с" if dur else "") + ")")
        if names:
            # A/B: видно, что именно даёт словарь
            await run_one(path, None, "без словаря:")
            await run_one(path, names, "со словарём:")
        else:
            await run_one(path, None, "результат:")
        print()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    names_arg = next((a for a in sys.argv[1:] if a.startswith("--names=")), None)
    names = names_arg.split("=", 1)[1].split(",") if names_arg else None
    if not args:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(args, names))
