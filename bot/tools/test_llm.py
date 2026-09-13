"""Живая проверка LLM на данных из smoke-БД: python -m tools.test_llm"""
import asyncio, json, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["DB_PATH"] = "data/smoke.sqlite3"
from app import db, llm, render
from app.config import settings

async def main():
    await db.init()
    st = (await db.students((await db.groups())[0]["id"]))[0]
    print(f"модель {settings.llm_model} @ {settings.llm_base_url}")
    data = await llm.generate(st, await db.student_answers(st["id"]),
                              await db.group_answers(st["group_id"]))
    if data.get("_error"):
        print("ОШИБКА:", data["_error"])
    else:
        print("ключи:", sorted(data.keys()))
        print("summary:", data.get("summary", "")[:300])
        print("strengths:", json.dumps(data.get("strengths"), ensure_ascii=False)[:400])
        print("growth:", json.dumps(data.get("growth"), ensure_ascii=False)[:300])
        print("roadmap кварталов:", len(data.get("roadmap") or []))
        print("HTML:", render.render_html(st, data, mentors="Азиз").name)
    await db.close()

asyncio.run(main())
