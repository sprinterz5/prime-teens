import { randomBytes } from "node:crypto";
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { forbidden } from "@/lib/auth/authorize";
import { currentStudent } from "@/lib/live-student";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Issues (or with { rotate: true } replaces) the secret calendar feed link.
 * Calendar apps fetch it without cookies, so the token is the only key —
 * rotating it cuts off any copy of the old link.
 */
export async function POST(request: Request) {
  const student = await currentStudent();
  if (!student) return forbidden();
  const body = await request.json().catch(() => null);

  const row = await prisma.student.findUnique({ where: { id: student.id }, select: { calendarToken: true } });
  let token = row?.calendarToken ?? null;
  if (!token || body?.rotate === true) {
    token = randomBytes(24).toString("base64url");
    await prisma.student.update({ where: { id: student.id }, data: { calendarToken: token } });
  }
  return NextResponse.json({ ok: true, path: `/api/calendar/feed/${token}.ics` });
}
