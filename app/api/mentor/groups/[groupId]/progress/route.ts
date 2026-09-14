import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canAccessGroup, forbidden, unauthorized } from "@/lib/auth/authorize";
import { courseDays, fieldsPerDay, getField } from "@/lib/workbook/manifest";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function isFilled(fieldType: "text" | "textarea" | "checkbox" | "canvas", value: unknown): boolean {
  if (fieldType === "checkbox") return value === true;
  if (fieldType === "text" || fieldType === "textarea") return typeof value === "string" && value.trim().length > 0;
  return true; // canvas: presence of a drawings row already means "filled"
}

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
  const studentIds = students.map((s) => s.id);

  const [entries, drawings] = await Promise.all([
    prisma.workbookEntry.findMany({ where: { studentId: { in: studentIds } } }),
    prisma.workbookDrawing.findMany({ where: { studentId: { in: studentIds } } })
  ]);

  type Row = { dayFilled: Record<number, number>; lastActivity: Date | null };
  const perStudent = new Map<number, Row>(studentIds.map((id) => [id, { dayFilled: {}, lastActivity: null }]));

  function touch(studentId: number, fieldId: string, value: unknown, updatedAt: Date) {
    const field = getField(fieldId);
    const row = perStudent.get(studentId);
    if (!row) return;
    if (!row.lastActivity || updatedAt > row.lastActivity) row.lastActivity = updatedAt;
    if (!field || field.day === null) return;
    if (isFilled(field.type, value)) {
      row.dayFilled[field.day] = (row.dayFilled[field.day] ?? 0) + 1;
    }
  }

  for (const e of entries) touch(e.studentId, e.fieldId, e.value, e.updatedAt);
  for (const d of drawings) touch(d.studentId, d.fieldId, true, d.updatedAt);

  const result = students.map((s) => {
    const row = perStudent.get(s.id)!;
    const percentByDay: Record<number, number> = {};
    for (const day of courseDays) {
      const total = fieldsPerDay[day] ?? 0;
      const filled = row.dayFilled[day] ?? 0;
      percentByDay[day] = total > 0 ? Math.round((filled / total) * 100) : 0;
    }
    return {
      id: s.id,
      fullName: s.fullName,
      shortName: s.shortName,
      filledByDay: row.dayFilled,
      percentByDay,
      lastActivity: row.lastActivity ? row.lastActivity.toISOString() : null
    };
  });

  return NextResponse.json({ days: courseDays, totalsByDay: fieldsPerDay, students: result });
}
