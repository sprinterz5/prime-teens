import { prisma } from "@/lib/prisma";
import { courseDays, fieldsPerDay, getField, type FieldType } from "@/lib/workbook/manifest";

export type StudentWorkbookProgress = {
  dayFilled: Record<number, number>;
  percentByDay: Record<number, number>;
  lastActivity: Date | null;
};

function isFilled(fieldType: FieldType, value: unknown): boolean {
  if (fieldType === "checkbox") return value === true;
  if (fieldType === "text" || fieldType === "textarea") return typeof value === "string" && value.trim().length > 0;
  return true; // canvas: presence of a drawings row already means "filled"
}

/** Per-student "% of the day's workbook fields filled" — the mentor table and the student's own course page. */
export async function workbookProgress(studentIds: number[]): Promise<Map<number, StudentWorkbookProgress>> {
  const [entries, drawings] = await Promise.all([
    prisma.workbookEntry.findMany({ where: { studentId: { in: studentIds } } }),
    prisma.workbookDrawing.findMany({ where: { studentId: { in: studentIds } } })
  ]);

  const perStudent = new Map<number, StudentWorkbookProgress>(
    studentIds.map((id) => [id, { dayFilled: {}, percentByDay: {}, lastActivity: null }])
  );

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

  for (const row of perStudent.values()) {
    for (const day of courseDays) {
      const total = fieldsPerDay[day] ?? 0;
      const filled = row.dayFilled[day] ?? 0;
      row.percentByDay[day] = total > 0 ? Math.round((filled / total) * 100) : 0;
    }
  }
  return perStudent;
}
