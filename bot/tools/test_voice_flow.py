"""Проверка логики голосовых ответов без Telegram: python -m tools.test_voice_flow

Что проверяем:
  1. режимы confirm (always / smart / never) на уверенной и сомнительной расшифровке;
  2. что ответ реально переписывается в БД и старый текст не остаётся;
  3. что текстовые и голосовые ответы кладутся в одну и ту же колонку и
     отличаются только полем source.
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools._pgtest import TEST_DATABASE_URL  # noqa: E402

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from tools import _pgtest as pgtest  # noqa: E402
from app import db  # noqa: E402
from app.config import COURSE  # noqa: E402
from app.handlers.checklist import _needs_confirm  # noqa: E402
from app.stt import Transcript  # noqa: E402

SURE = Transcript("Алия сегодня разговорилась", -0.25)
SHAKY = Transcript("оружие отвлекалось на телефон", -0.95)
REMOTE = Transcript("удалённый провайдер уверенности не даёт", None)


def check(mode: str, expected: dict[str, bool]) -> bool:
    COURSE.setdefault("voice", {})["confirm"] = mode
    ok = True
    for label, tr in (("уверенная", SURE), ("сомнительная", SHAKY), ("без оценки", REMOTE)):
        got = _needs_confirm(tr)
        want = expected[label]
        mark = "ok " if got == want else "ОШИБКА"
        ok &= got == want
        print(f"  {mark} confirm={mode:6} {label:14} -> спросить={got} (ждали {want})")
    return ok


def check_truncation() -> bool:
    """Длинная запись + куцый текст = whisper оборвался, даже если он «уверен»."""
    COURSE["voice"]["confirm"] = "smart"
    cases = [
        ("20 с, 4 слова (обрыв)", Transcript("Алия сегодня была молодец", -0.2), 20, True),
        ("20 с, 40 слов (норма)", Transcript(" ".join(["слово"] * 40), -0.2), 20, False),
        ("5 с, 3 слова (коротко, но и запись короткая)",
         Transcript("всё было нормально", -0.2), 5, False),
        ("длительность неизвестна", Transcript("два слова", -0.2), None, False),
    ]
    ok = True
    for label, tr, secs, want in cases:
        got = _needs_confirm(tr, secs)
        mark = "ok " if got == want else "ОШИБКА"
        ok &= got == want
        print(f"  {mark} {label:46} -> спросить={got} (ждали {want})")
    return ok


async def main() -> None:
    print("--- режимы подтверждения ---")
    all_ok = True
    all_ok &= check("always", {"уверенная": True, "сомнительная": True, "без оценки": True})
    all_ok &= check("smart", {"уверенная": False, "сомнительная": True, "без оценки": False})
    all_ok &= check("never", {"уверенная": False, "сомнительная": False, "без оценки": False})

    print("\n--- обрыв расшифровки (слов в секунду) ---")
    all_ok &= check_truncation()

    COURSE["voice"]["confirm"] = "smart"

    print("\n--- переписывание ответа ---")
    await pgtest.prepare()
    await db.init()
    gid = await db.upsert_group("Тест", "2026-08-03", "10:00")
    sid = await db.add_student(gid, "Образцова Аружан")
    mid = await db.register_mentor(1, "+77010000000", "Ментор")
    ses = await db.open_session(mid, gid, 1)

    aid = await db.save_answer(ses, gid, 1, "observation", "Что заметил?", "observations",
                               sid, None, "оружие отвлекалось на телефон", "voice")
    print(f"  сохранён ответ id={aid}: {(await db.answer(aid))['text']!r}")

    await db.update_answer(aid, "Аружан отвлекалась на телефон", "text")
    row = await db.answer(aid)
    print(f"  после правки:        {row['text']!r}, source={row['source']}")

    rows = await db.q("SELECT * FROM answers WHERE session_id = ?", ses)
    dup = len(rows) != 1
    print(f"  записей в сессии: {len(rows)} (ждали 1, дубля быть не должно)")
    all_ok &= not dup
    all_ok &= row["text"] == "Аружан отвлекалась на телефон"

    print("\n--- текст и голос в одной колонке ---")
    a_txt = await db.save_answer(ses, gid, 1, "q_txt", "Вопрос", None, sid, None,
                                 "ответ текстом", "text")
    a_voc = await db.save_answer(ses, gid, 1, "q_voc", "Вопрос", None, sid, None,
                                 "ответ голосом", "voice")
    for a in (a_txt, a_voc):
        r = await db.answer(a)
        print(f"  id={r['id']} source={r['source']:5} text={r['text']!r}")

    await db.close()
    print("\n" + ("ВСЁ ОК" if all_ok else "ЕСТЬ ОШИБКИ"))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
