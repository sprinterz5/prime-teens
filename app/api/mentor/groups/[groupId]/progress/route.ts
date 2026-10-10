import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canAccessGroup, forbidden, unauthorized } from "@/lib/auth/authorize";
import { courseDays, fieldsPerDay } from "@/lib/workbook/manifest";
import { workbookProgress } from "@/lib/workbook/progress";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

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
    where: { groupId },
    orderBy: { fullName: "asc" },
    select: { id: true, fullName: true, shortName: true }
  });
  const progress = await workbookProgress(students.map((s) => s.id));

  const result = students.map((s) => {
    const row = progress.get(s.id)!;
    return {
      id: s.id,
      fullName: s.fullName,
      shortName: s.shortName,
      filledByDay: row.dayFilled,
      percentByDay: row.percentByDay,
      lastActivity: row.lastActivity ? row.lastActivity.toISOString() : null
    };
  });

  return NextResponse.json({ days: courseDays, totalsByDay: fieldsPerDay, students: result });
}
