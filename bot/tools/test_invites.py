"""Проверка пригласительных ссылок без Telegram: python -m tools.test_invites

Что проверяем:
  1. создание токена приглашения и поиск по нему;
  2. отзыв — запись остаётся (revoked=1), но active_invite её больше не находит,
     а повторный отзыв несуществующего токена не падает и возвращает False;
  3. персональная (student_id задан) ссылка одноразовая: второй заход другим
     tg отвергается (used_by_other), тем же tg — проходит без ошибки
     (used_by_self, статус до и после claim не меняется на «занято чужим»).
  4. менторская ссылка (role='mentor') теперь ТОЖЕ одноразовая — раньше была
     многоразовой групповой, с переходом на Excel-импорт стала просто
     пропуском в бота без группы: claim_invite помечает её использованной
     точно так же, как персональную, а её group_id не участвует ни в какой
     привязке (см. db.py и handlers/registration.py:_link_mentor_from_roster).
  5. отозванная ссылка не работает независимо от типа.
  6. повторный вызов «Ссылки для учеников» переиспользует токен, если у
     ученика уже есть живая неиспользованная ссылка — не плодит дубли.
  7. роли: только-админ (is_mentor=0) не попадает в выборку для /broadcast,
     а bootstrap-пользователь (is_admin=1 И is_mentor=1) получает обе роли.

Примечание: раньше здесь же проверялся порог похожести названий групп
(difflib) из мастера /setup — мастер отключён (см. заголовок
app/handlers/setup.py, заменён Excel-импортом), эта проверка убрана вместе
с ним.
"""
from __future__ import annotations

import asyncio
import os
import secrets
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools._pgtest import TEST_DATABASE_URL  # noqa: E402

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from tools import _pgtest as pgtest  # noqa: E402
from app import db  # noqa: E402


async def main() -> None:
    await pgtest.prepare()
    await db.init()
    all_ok = True

    print("--- токены приглашений ---")
    gid = await db.upsert_group("Тестовая группа", "2026-09-07")
    token = secrets.token_urlsafe(8)
    await db.create_invite(token, gid, created_by=1)

    row = await db.invite_by_token(token)
    ok = row is not None and row["group_id"] == gid and row["revoked"] is False
    print(f"  создан и находится по токену: {ok}")
    all_ok &= ok

    ok = await db.invite_by_token("no-such-token") is None
    print(f"  несуществующий токен не находится: {ok}")
    all_ok &= ok

    ok = await db.active_invite(token) is not None
    print(f"  active_invite видит живой токен: {ok}")
    all_ok &= ok

    print("\n--- отзыв ---")
    revoked = await db.revoke_invite(token)
    print(f"  revoke_invite вернул True: {revoked}")
    all_ok &= revoked

    row = await db.invite_by_token(token)
    ok = row is not None and row["revoked"] is True
    print(f"  запись осталась в базе, но revoked=1: {ok}")
    all_ok &= ok

    ok = await db.active_invite(token) is None
    print(f"  active_invite отозванный токен больше не находит: {ok}")
    all_ok &= ok

    ok = (await db.revoke_invite("no-such-token")) is False
    print(f"  повторный отзыв несуществующего токена — False, не падает: {ok}")
    all_ok &= ok

    print("\n--- персональная ссылка ученика: одноразовая ---")
    sid = await db.add_student(gid, "Тестовый Ученик")
    stoken = secrets.token_urlsafe(8)
    await db.create_invite(stoken, gid, created_by=1, role="student", student_id=sid)

    ok = await db.invite_status(stoken, tg_user_id=1001) == "ok"
    print(f"  свежая персональная ссылка -> статус ok: {ok}")
    all_ok &= ok

    claimed = await db.claim_invite(stoken, tg_user_id=1001)
    ok = claimed == "ok"
    print(f"  первый заход (tg=1001) claim -> ok: {ok}")
    all_ok &= ok

    row = await db.invite_by_token(stoken)
    ok = row is not None and row["used_by_tg"] == 1001 and row["used_at"] is not None
    print(f"  used_by_tg/used_at проставлены: {ok}")
    all_ok &= ok

    status_other = await db.invite_status(stoken, tg_user_id=2002)
    ok = status_other == "used_by_other"
    print(f"  второй заход другим tg (2002) -> used_by_other: {ok}")
    all_ok &= ok

    claimed_other = await db.claim_invite(stoken, tg_user_id=2002)
    ok = claimed_other == "used_by_other"
    print(f"  claim другим tg тоже отвергается: {ok}")
    all_ok &= ok

    status_self = await db.invite_status(stoken, tg_user_id=1001)
    ok = status_self == "used_by_self"
    print(f"  повторный заход тем же tg (1001) -> used_by_self, не ошибка: {ok}")
    all_ok &= ok

    claimed_self = await db.claim_invite(stoken, tg_user_id=1001)
    ok = claimed_self == "used_by_self"
    print(f"  claim тем же tg -> used_by_self (не перезаписывает used_at): {ok}")
    all_ok &= ok

    print("\n--- менторская ссылка: одноразовая, group_id ничего не значит ---")
    # group_id тут — заглушка для NOT NULL/FK (см. admin.py:_placeholder_group_id),
    # намеренно берём ЧУЖУЮ группу, чтобы доказать: значения не имеет —
    # привязка идёт через roster по телефону, а не через invites.group_id.
    mtoken = secrets.token_urlsafe(8)
    await db.create_invite(mtoken, gid, created_by=1, role="mentor")

    ok = await db.invite_status(mtoken, tg_user_id=3003) == "ok"
    print(f"  свежая менторская ссылка -> статус ok (не multi, как раньше): {ok}")
    all_ok &= ok

    claimed = await db.claim_invite(mtoken, tg_user_id=3003)
    ok = claimed == "ok"
    print(f"  первый заход (tg=3003) claim -> ok: {ok}")
    all_ok &= ok

    row = await db.invite_by_token(mtoken)
    ok = row is not None and row["used_by_tg"] == 3003 and row["used_at"] is not None
    print(f"  used_by_tg/used_at проставлены — ссылка одноразовая, как персональная: {ok}")
    all_ok &= ok

    ok = await db.claim_invite(mtoken, tg_user_id=4004) == "used_by_other"
    print(f"  второй заход другим tg (4004) -> used_by_other (не multi): {ok}")
    all_ok &= ok

    print("\n--- группа ментора берётся из roster по телефону, не из ссылки ---")
    from app.handlers.registration import _link_mentor_from_roster  # noqa: E402

    other_gid = await db.upsert_group("Другая тестовая группа", "2026-09-14")
    await db.add_to_roster("+77020000009", "Ростер Тест", other_gid, is_admin=False, is_mentor=True)
    new_mentor_id = await db.register_mentor(20009, "+77020000009", "Ростер Тест")
    linked_name = await _link_mentor_from_roster(await db.mentor_by_tg(20009))
    ok = linked_name == "Другая тестовая группа"
    print(f"  _link_mentor_from_roster нашёл группу по телефону: {ok}")
    all_ok &= ok

    groups_of_mentor = await db.mentor_groups(new_mentor_id)
    ok = any(g["id"] == other_gid for g in groups_of_mentor)
    print(f"  группа реально привязана в mentor_groups: {ok}")
    all_ok &= ok

    await db.register_mentor(20010, "+77020000010", "Без Ростера")
    linked_none = await _link_mentor_from_roster(await db.mentor_by_tg(20010))
    ok = linked_none is None
    print(f"  номера нет в roster -> _link_mentor_from_roster вернул None, не упал: {ok}")
    all_ok &= ok

    print("\n--- отозванная ссылка не работает ни в каком виде ---")
    rtoken = secrets.token_urlsafe(8)
    await db.create_invite(rtoken, gid, created_by=1, role="mentor")
    await db.revoke_invite(rtoken)
    ok = await db.invite_status(rtoken, tg_user_id=5005) == "revoked"
    print(f"  отозванная групповая ссылка -> revoked: {ok}")
    all_ok &= ok
    ok = await db.claim_invite(rtoken, tg_user_id=5005) == "revoked"
    print(f"  claim отозванной ссылки тоже revoked (не помечает used): {ok}")
    all_ok &= ok

    rtoken2 = secrets.token_urlsafe(8)
    sid2 = await db.add_student(gid, "Второй Ученик")
    await db.create_invite(rtoken2, gid, created_by=1, role="student", student_id=sid2)
    await db.revoke_invite(rtoken2)
    ok = await db.invite_status(rtoken2, tg_user_id=6006) == "revoked"
    print(f"  отозванная персональная ссылка -> revoked (не ok/used_by_*): {ok}")
    all_ok &= ok

    print("\n--- переиспользование неиспользованной ссылки ученика (не плодит дубли) ---")
    sid3 = await db.add_student(gid, "Третий Ученик")
    first_token = secrets.token_urlsafe(8)
    await db.create_invite(first_token, gid, created_by=1, role="student", student_id=sid3)
    reused = await db.active_student_invite(sid3)
    ok = reused is not None and reused["token"] == first_token
    print(f"  active_student_invite находит ту же неиспользованную ссылку: {ok}")
    all_ok &= ok

    # тот же сценарий, что и в admin.py: «уже есть — переиспользуем токен»
    existing = await db.active_student_invite(sid3)
    token_to_use = existing["token"] if existing else secrets.token_urlsafe(8)
    ok = token_to_use == first_token
    print(f"  повторный вызов «Ссылки для учеников» берёт тот же токен: {ok}")
    all_ok &= ok

    total_for_sid3 = await db.q("SELECT COUNT(*) AS c FROM invites WHERE student_id = ?", sid3)
    ok = total_for_sid3[0]["c"] == 1
    print(f"  в базе на ученика ровно один токен, дубля нет: {ok}")
    all_ok &= ok

    # а вот когда ссылку использовали — новый вызов должен завести новую (не reuse чужой использованной)
    await db.claim_invite(first_token, tg_user_id=7007)
    reused_after_use = await db.active_student_invite(sid3)
    ok = reused_after_use is None
    print(f"  после использования active_student_invite её больше не находит "
          f"(следующий вызов создаст новую): {ok}")
    all_ok &= ok

    print("\n--- роли: is_admin/is_mentor независимы ---")
    only_admin_id = await db.register_mentor(
        8008, "+77010000001", "Только Админ", is_admin=True, is_mentor=False,
    )
    mentor_id = await db.register_mentor(
        9009, "+77010000002", "Только Ментор", is_admin=False, is_mentor=True,
    )
    bootstrap_id = await db.register_mentor(
        1010, "+77010000003", "Бутстрап", is_admin=True, is_mentor=True,
    )

    broadcast_targets = {r["tg_user_id"] for r in await db.q(
        "SELECT tg_user_id FROM mentors WHERE is_mentor"
    )}
    ok = 8008 not in broadcast_targets
    print(f"  только-админ НЕ в выборке для /broadcast: {ok}")
    all_ok &= ok
    ok = 9009 in broadcast_targets and 1010 in broadcast_targets
    print(f"  ментор и bootstrap-пользователь в выборке для /broadcast: {ok}")
    all_ok &= ok

    bootstrap_row = await db.q1("SELECT is_admin, is_mentor FROM mentors WHERE tg_user_id = ?",
                                1010)
    ok = bool(bootstrap_row["is_admin"]) and bool(bootstrap_row["is_mentor"])
    print(f"  bootstrap-пользователь получил ОБЕ роли (is_admin=1, is_mentor=1): {ok}")
    all_ok &= ok

    # регистрация повторно с меньшими правами не отбирает уже выданные (MAX-merge)
    await db.register_mentor(8008, "+77010000001", "Только Админ", is_admin=False, is_mentor=False)
    still_admin = await db.q1("SELECT is_admin, is_mentor FROM mentors WHERE tg_user_id = ?", 8008)
    ok = bool(still_admin["is_admin"]) and not bool(still_admin["is_mentor"])
    print(f"  повторная регистрация не отбирает уже выданную роль (MAX-merge): {ok}")
    all_ok &= ok

    await db.close()
    print("\n" + ("ВСЁ ОК" if all_ok else "ЕСТЬ ОШИБКИ"))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
