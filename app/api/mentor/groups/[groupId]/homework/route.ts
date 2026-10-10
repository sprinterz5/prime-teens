import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canAccessGroup, forbidden, unauthorized } from "@/lib/auth/authorize";
import { courseDaysList } from "@/lib/course";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Every homework submission of one group, plus the course days that have homework. */
export async function GET(_request: Request, { params }: { params: Promise<{ groupId: string }> }) {
  const session = await getSession();
  if (!session) return unauthorized();
  if (session.role === "student") return forbidden();

  const groupId = Number((await params).groupId);
  if (!Number.isInteger(groupId)) {
    return NextResponse.json({ ok: false, message: "Некорректный groupId" }, { status: 400 });
  }
  if (!(await canAccessGroup(session, groupId))) return forbidden();

  const students = await prisma.student.findMany({
    where: { groupId, active: true },
    orderBy: { fullName: "asc" },
    select: { id: true, fullName: true, shortName: true }
  });
  const submissions = await prisma.homework.findMany({
    where: { studentId: { in: students.map((s) => s.id) } },
    include: { reviewer: { select: { fullName: true } } }
  });

  return NextResponse.json({
    days: courseDaysList.filter((d) => d.homework).map((d) => ({ index: d.index, title: d.title, homework: d.homework })),
    students,
    submissions: submissions.map((h) => ({
      studentId: h.studentId,
      dayIndex: h.dayIndex,
      text: h.text,
      status: h.status,
      mentorComment: h.mentorComment,
      submittedAt: h.submittedAt.toISOString(),
      reviewedAt: h.reviewedAt?.toISOString() ?? null,
      reviewerName: h.reviewer?.fullName ?? null
    }))
  });
}
