import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { verifyTelegramInitData } from "@/lib/auth/telegram";
import { applySessionCookie, newSessionPayload } from "@/lib/auth/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  const initData = body?.initData;
  if (typeof initData !== "string" || !initData) {
    return NextResponse.json({ ok: false, message: "Отсутствует initData" }, { status: 400 });
  }

  const kidsToken = process.env.TELEGRAM_KIDS_BOT_TOKEN ?? "";
  const mentorToken = process.env.TELEGRAM_MENTOR_BOT_TOKEN ?? "";

  // Try the kids bot first (students), then the mentor bot (mentors/admins).
  if (kidsToken) {
    const verified = verifyTelegramInitData(initData, kidsToken);
    if (verified.ok) {
      const student = await prisma.student.findUnique({
        where: { tgUserId: BigInt(verified.result.user.id) }
      });
      if (student?.active) {
        const res = NextResponse.json({ ok: true, role: "student" as const });
        applySessionCookie(
          res,
          newSessionPayload({
            role: "student",
            studentId: student.id,
            tgUserId: String(verified.result.user.id)
          })
        );
        return res;
      }
    }
  }

  if (mentorToken) {
    const verified = verifyTelegramInitData(initData, mentorToken);
    if (verified.ok) {
      const mentor = await prisma.mentor.findUnique({
        where: { tgUserId: BigInt(verified.result.user.id) }
      });
      if (mentor) {
        const res = NextResponse.json({ ok: true, role: mentor.isAdmin ? "admin" : "mentor" });
        applySessionCookie(
          res,
          newSessionPayload({
            role: mentor.isAdmin ? "admin" : "mentor",
            mentorId: mentor.id,
            tgUserId: String(verified.result.user.id)
          })
        );
        return res;
      }
    }
  }

  return NextResponse.json(
    { ok: false, message: "Не удалось подтвердить Telegram-аккаунт" },
    { status: 401 }
  );
}
