from aiogram import Router

from app.kids.handlers import feedback, hackathon, misc, registration


def build_router() -> Router:
    root = Router(name="kids-root")
    # feedback и hackathon первыми: пока идёт их FSM-флоу (например, ввод
    # названия команды), их хендлеры должны перехватывать текст раньше
    # общих кнопок меню — тот же приём, что и в боте ментора
    # (app/handlers/__init__.py, checklist первым).
    root.include_router(feedback.router)
    root.include_router(hackathon.router)
    root.include_router(registration.router)
    root.include_router(misc.router)
    return root
