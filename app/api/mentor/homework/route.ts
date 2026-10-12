import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canReadStudent, forbidden, unauthorized } from "@/lib/auth/authorize";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const COMMENT_MAX_LENGTH = 2000;

/**
 * A mentor accepts or returns one submission: { studentId, day, status:
 * "accepted" | "returned", comment?, submittedAt }. submittedAt is the
 * version the mentor read: if the student resubmitted since, nothing is
 * changed (409) rather than accepting text nobody saw. Clearing notified_at hands the news
 * to the kids bot, which tells the student (bot/app/kids/scheduler.py).
 */
export async function POST(request: Request) {
  const session = await getSession();
  if (!session) return unauthorized();
  if (session.role === "student" || !session.mentorId) return forbidden();

  const body = await request.json().catch(() => null);
  const studentId = Number(body?.studentId);
  const dayIndex = Number(body?.day);
  const status = body?.status;
  const comment = typeof body?.comment === "string" ? body.comment.trim() : "";
  const submittedAt = new Date(typeof body?.submittedAt === "string" ? body.submittedAt : NaN);
  if (
    !Number.isInteger(studentId) ||
    !Number.isInteger(dayIndex) ||
    (status !== "accepted" && status !== "returned") ||
    Number.isNaN(submittedAt.getTime())
  ) {
    return NextResponse.json({ ok: false, message: "Некорректный запрос" }, { status: 400 });
  }
  if (status === "returned" && !comment) {
    return NextResponse.json({ ok: false, message: "Напишите, что доработать" }, { status: 400 });
  }
  if (comment.length > COMMENT_MAX_LENGTH) {
    return NextResponse.json({ ok: false, message: `Не больше ${COMMENT_MAX_LENGTH} символов` }, { status: 400 });
  }
  if (!(await canReadStudent(session, studentId))) return forbidden();

  const updated = await prisma.homework.updateMany({
    where: { studentId, dayIndex, submittedAt },
    data: {
      status,
      mentorComment: comment || null,
      reviewedAt: new Date(),
      reviewedBy: session.mentorId,
      notifiedAt: null
    }
  });
  if (updated.count === 0) {
    const exists = await prisma.homework.findUnique({ where: { studentId_dayIndex: { studentId, dayIndex } } });
    return exists
      ? NextResponse.json({ ok: false, message: "Ученик успел обновить ответ — посмотрите новую версию" }, { status: 409 })
      : NextResponse.json({ ok: false, message: "Ученик ещё не сдал эту домашку" }, { status: 404 });
  }
  return NextResponse.json({ ok: true });
}
