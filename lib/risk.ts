import { prisma } from "@/lib/prisma";
import { courseDaysList, homeworkDue, lessonStart } from "@/lib/course";
import { courseDays as workbookDays } from "@/lib/workbook/manifest";
import { workbookProgress } from "@/lib/workbook/progress";

/**
 * "К кому подойти": students showing signs of falling behind, from data the
 * platform and the mentor bot already collect. Only lessons that have
 * already ended count; a signal needs a pattern (two recent lessons), not a
 * single bad day. For mentors only — students never see this.
 */

const RECENT_LESSONS = 2;

export type RiskStudent = {
  id: number;
  name: string;
  reasons: string[];
};

export async function groupRisk(groupId: number, now = new Date()): Promise<{ recentDays: number[]; students: RiskStudent[] }> {
  const group = await prisma.group.findUnique({ where: { id: groupId } });
  if (!group) return { recentDays: [], students: [] };

  const past = courseDaysList.filter((d) => {
    const start = lessonStart(group, d);
    return start && start.getTime() + d.durationMinutes * 60_000 < now.getTime();
  });
  const recent = past.slice(-RECENT_LESSONS).map((d) => d.index);
  if (recent.length === 0) return { recentDays: [], students: [] };

  const students = await prisma.student.findMany({
    where: { groupId, active: true },
    orderBy: { fullName: "asc" },
    select: { id: true, fullName: true }
  });
  const ids = students.map((s) => s.id);

  const overdueDays = past
    .filter((d) => d.homework)
    .filter((d) => {
      const due = homeworkDue(group, d);
      return due && due.getTime() < now.getTime();
    })
    .map((d) => d.index);

  const [marks, progress, homework, liveSessions] = await Promise.all([
    // Per-student marks from the mentor's post-lesson survey (bot/app/handlers/checklist.py, "<key>_mark").
    prisma.answer.findMany({
      where: { groupId, studentId: { in: ids }, dayIndex: { in: recent }, questionKey: { in: ["absent_mark", "struggled_mark"] } },
      select: { studentId: true, dayIndex: true, questionKey: true }
    }),
    workbookProgress(ids),
    prisma.homework.findMany({ where: { studentId: { in: ids }, dayIndex: { in: overdueDays } }, select: { studentId: true, dayIndex: true } }),
    prisma.liveSession.findMany({
      where: { groupId, finishedAt: { not: null } },
      orderBy: { startedAt: "desc" },
      take: RECENT_LESSONS,
      select: { id: true, answers: { select: { studentId: true }, distinct: ["studentId"] } }
    })
  ]);

  const daysMarked = (studentId: number, key: string) =>
    new Set(marks.filter((m) => m.studentId === studentId && m.questionKey === key).map((m) => m.dayIndex)).size;
  const submitted = new Set(homework.map((h) => `${h.studentId}:${h.dayIndex}`));
  const recentWorkbookDays = recent.filter((d) => workbookDays.includes(d));

  const result: RiskStudent[] = [];
  for (const s of students) {
    const reasons: string[] = [];

    const absent = daysMarked(s.id, "absent_mark");
    if (absent >= RECENT_LESSONS) reasons.push(`не было на последних ${absent} занятиях`);

    const struggled = daysMarked(s.id, "struggled_mark");
    if (struggled >= RECENT_LESSONS) reasons.push(`не шло на последних ${struggled} занятиях`);

    const pct = progress.get(s.id)?.percentByDay ?? {};
    if (recentWorkbookDays.length >= RECENT_LESSONS && recentWorkbookDays.every((d) => !pct[d])) {
      reasons.push(`пустая тетрадь за дни ${recentWorkbookDays.join(", ")}`);
    }

    const missing = overdueDays.filter((d) => !submitted.has(`${s.id}:${d}`));
    if (missing.length >= RECENT_LESSONS) reasons.push(`нет домашки за дни ${missing.join(", ")}`);

    if (liveSessions.length >= RECENT_LESSONS && liveSessions.every((l) => !l.answers.some((a) => a.studentId === s.id))) {
      reasons.push(`нет ответов в последних ${liveSessions.length} live`);
    }

    if (reasons.length) result.push({ id: s.id, name: s.fullName, reasons });
  }
  result.sort((a, b) => b.reasons.length - a.reasons.length);
  return { recentDays: recent, students: result };
}
