from aiogram import Router

from app.config import settings
from app.handlers import admin, admin_panel, characteristics, checklist, export, registration

# setup — мастер /setup — отключён: группы/менторы/ученики теперь приходят
# Excel-импортом (см. admin.py: /template, _import_excel). Модуль не удалён,
# только закомментирован целиком (см. заголовок app/handlers/setup.py) —
# если Excel-путь когда-нибудь не подойдёт, раскомментируй импорт ниже и
# строку router.include_router(setup.router).
# from app.handlers import setup


def build_router() -> Router:
    root = Router(name="root")
    # checklist первым: пока идёт опрос, его state-хендлеры должны
    # перехватывать текстовый ввод раньше общих команд
    root.include_router(checklist.router)
    # root.include_router(setup.router)
    root.include_router(registration.router)
    root.include_router(export.router)
    if settings.experimental_characteristics:
        root.include_router(characteristics.router)
    root.include_router(admin_panel.router)
    root.include_router(admin.router)
    return root
