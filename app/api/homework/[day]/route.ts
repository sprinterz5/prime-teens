import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { forbidden, unauthorized } from "@/lib/auth/authorize";
import { archivedResponse, getStudentGroupInfo } from "@/lib/workbook/archive";
import { getCourseDay } from "@/lib/course";
import { HOMEWORK_MAX_LENGTH } from "@/lib/homework";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * A student submits (or edits) their homework for one course day. Any edit
 * sends it back to "на проверке" and clears the review, so the kids bot
 * notifies again after the next review (see bot/app/kids/scheduler.py).
 * The mentor's last comment stays visible next to the new version.
 */
export async function PUT(request: Request, { params }: { params: Promise<{ day: string }> }) {
  const session = await getSession();
  if (!session) return unauthorized();
  if (session.role !== "student" || !session.studentId) return forbidden();
  const studentId = session.studentId;

  const dayIndex = Number((await params).day);
  const day = Number.isInteger(dayIndex) ? getCourseDay(dayIndex) : undefined;
  if (!day?.homework) {
    return NextResponse.json({ ok: false, message: "К этому дню домашки нет" }, { status: 404 });
  }

  const body = await request.json().catch(() => null);
  const text = typeof body?.text === "string" ? body.text.trim() : "";
  if (!text) return NextResponse.json({ ok: false, message: "Напишите ответ" }, { status: 400 });
  if (text.length > HOMEWORK_MAX_LENGTH) {
    return NextResponse.json({ ok: false, message: `Не больше ${HOMEWORK_MAX_LENGTH} символов` }, { status: 400 });
  }

  const groupInfo = await getStudentGroupInfo(studentId);
  if (!groupInfo) return NextResponse.json({ ok: false, message: "Ученик не найден" }, { status: 404 });
  if (groupInfo.archivedAt) return archivedResponse();

  const existing = await prisma.homework.findUnique({ where: { studentId_dayIndex: { studentId, dayIndex } } });
  if (existing?.status === "accepted") {
    return NextResponse.json({ ok: false, message: "Домашка уже принята — менять её не нужно" }, { status: 409 });
  }

  const reset = { text, status: "submitted", submittedAt: new Date(), reviewedAt: null, reviewedBy: null, notifiedAt: null };
  const saved = await prisma.homework.upsert({
    where: { studentId_dayIndex: { studentId, dayIndex } },
    create: { studentId, dayIndex, ...reset },
    update: reset
  });

  return NextResponse.json({
    ok: true,
    homework: {
      text: saved.text,
      status: saved.status,
      mentorComment: saved.mentorComment,
      submittedAt: saved.submittedAt.toISOString()
    }
  });
}
