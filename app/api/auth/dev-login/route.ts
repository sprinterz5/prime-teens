import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { applySessionCookie, newSessionPayload } from "@/lib/auth/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function devLoginEnabled(): boolean {
  return process.env.NODE_ENV !== "production" && process.env.DEV_LOGIN === "1";
}

export async function POST(request: Request) {
  if (!devLoginEnabled()) {
    return new NextResponse(null, { status: 404 });
  }

  const body = await request.json().catch(() => null);
  const kind = body?.kind;

  if (kind === "student") {
    const studentId = Number(body?.studentId);
    const student = await prisma.student.findUnique({ where: { id: studentId } });
    if (!student) return NextResponse.json({ ok: false, message: "Студент не найден" }, { status: 404 });
    const res = NextResponse.json({ ok: true, role: "student" as const, studentId: student.id });
    applySessionCookie(
      res,
      newSessionPayload({
        role: "student",
        studentId: student.id,
        tgUserId: student.tgUserId ? String(student.tgUserId) : `dev-student-${student.id}`
      })
    );
    return res;
  }

  if (kind === "mentor") {
    const mentorId = Number(body?.mentorId);
    const mentor = await prisma.mentor.findUnique({ where: { id: mentorId } });
    if (!mentor) return NextResponse.json({ ok: false, message: "Ментор не найден" }, { status: 404 });
    const role = mentor.isAdmin ? "admin" : "mentor";
    const res = NextResponse.json({ ok: true, role, mentorId: mentor.id });
    applySessionCookie(
      res,
      newSessionPayload({
        role,
        mentorId: mentor.id,
        tgUserId: String(mentor.tgUserId)
      })
    );
    return res;
  }

  return NextResponse.json({ ok: false, message: "Некорректный kind" }, { status: 400 });
}
