import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { loginPath } from "@/lib/auth/next-path";
import { AppHeader } from "@/components/app/app-header";
import { LiveBanner } from "@/components/live/live-banner";
import { courseDaysList, formatLesson, getCourseDay, homeworkDue } from "@/lib/course";
import { courseDays as workbookDays } from "@/lib/workbook/manifest";
import { HomeworkPanel } from "./homework-panel";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "День курса", robots: { index: false } };

export default async function CourseDayPage({ params }: { params: Promise<{ day: string }> }) {
  const dayIndex = Number((await params).day);
  const day = Number.isInteger(dayIndex) ? getCourseDay(dayIndex) : undefined;
  if (!day) notFound();

  const session = await getSession();
  if (!session) redirect(loginPath(`/course/day/${day.index}`));
  if (session.role !== "student" || !session.studentId) redirect("/mentor");

  const student = await prisma.student.findUnique({ where: { id: session.studentId }, include: { group: true } });
  if (!student) redirect("/login");
  const homework = day.homework
    ? await prisma.homework.findUnique({ where: { studentId_dayIndex: { studentId: student.id, dayIndex: day.index } } })
    : null;

  const position = courseDaysList.findIndex((d) => d.index === day.index);
  const prev = courseDaysList[position - 1];
  const next = courseDaysList[position + 1];
  const due = day.homework ? homeworkDue(student.group, day) : null;
  const hasWorkbook = workbookDays.includes(day.index);

  return (
    <div className="flex h-[100dvh] flex-col bg-navy-950 text-white">
      <AppHeader title={`День ${day.index} · ${day.title}`} backHref="/course" backLabel="Все дни" logout />
      <LiveBanner />

      <nav className="flex shrink-0 items-center justify-between gap-2 border-b border-white/10 px-3 py-1.5 text-xs text-muted">
        {prev ? (
          <Link href={`/course/day/${prev.index}`} className="hover:text-champagne">
            ← День {prev.index}
          </Link>
        ) : (
          <span />
        )}
        {next && (
          <Link href={`/course/day/${next.index}`} className="hover:text-champagne">
            День {next.index} →
          </Link>
        )}
      </nav>

      {day.homework && (
        <HomeworkPanel
          day={day.index}
          task={day.homework}
          due={due ? formatLesson(due) : null}
          readonly={!!student.group.archivedAt}
          initial={
            homework && {
              text: homework.text,
              status: homework.status,
              mentorComment: homework.mentorComment,
              submittedAt: homework.submittedAt.toISOString()
            }
          }
        />
      )}

      {hasWorkbook ? (
        <iframe
          key={day.index}
          src={`/workbook/frame?day=${day.index}`}
          title={`Рабочая тетрадь · день ${day.index}`}
          className="min-h-0 w-full flex-1 border-0"
        />
      ) : (
        <div className="flex flex-1 items-center justify-center px-6 text-center text-sm text-muted">
          В тетради нет страниц к этому дню.
        </div>
      )}
    </div>
  );
}
