import { NextResponse } from "next/server";
import { applySessionCookie } from "@/lib/auth/session";
import { consumeLogin, hashLoginToken, homePath } from "@/lib/auth/login-code";
import { clientIp, isLimited, recordFailure } from "@/lib/auth/rate-limit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const WINDOW_MS = 15 * 60 * 1000;
// Failed codes only: per address, and all addresses together so the 6-digit
// space can't be walked from many IPs either.
const PER_IP_LIMIT = 10;
const GLOBAL_LIMIT = 300;

/**
 * Exchanges a one-time login from the bots (/login) for a session cookie:
 * either { token } from the link (/login/<token>) or { code } typed on /login.
 */
export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  const token = typeof body?.token === "string" ? body.token.trim() : "";
  const code = typeof body?.code === "string" ? body.code.replace(/\D/g, "") : "";

  if (!token && code.length !== 6) {
    return NextResponse.json({ ok: false, message: "Введите 6 цифр из бота" }, { status: 400 });
  }
  const ipKey = `code:${clientIp(request)}`;
  if (code && (isLimited(ipKey, PER_IP_LIMIT) || isLimited("code:all", GLOBAL_LIMIT))) {
    return NextResponse.json(
      { ok: false, message: "Слишком много попыток. Подождите 15 минут или войдите по ссылке из бота." },
      { status: 429 }
    );
  }

  const session = await consumeLogin(token ? { tokenHash: hashLoginToken(token) } : { code });
  if (!session) {
    if (code) {
      recordFailure(ipKey, WINDOW_MS);
      recordFailure("code:all", WINDOW_MS);
    }
    return NextResponse.json(
      {
        ok: false,
        message: token
          ? "Ссылка устарела или уже использована. Отправьте боту /login ещё раз."
          : "Код не подошёл или устарел. Отправьте боту /login ещё раз."
      },
      { status: 401 }
    );
  }

  const res = NextResponse.json({ ok: true, redirect: homePath(session) });
  applySessionCookie(res, session);
  return res;
}
