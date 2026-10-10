import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { loginPath } from "@/lib/auth/next-path";
import { AppHeader } from "@/components/app/app-header";
import { LiveBanner } from "@/components/live/live-banner";
import { COURSE_TZ, courseDaysList, formatLesson, lessonStart, sameCourseDate } from "@/lib/course";
import { courseDays as workbookDays } from "@/lib/workbook/manifest";
import { workbookProgress } from "@/lib/workbook/progress";
import { homeworkStatusLabel, isHomeworkStatus } from "@/lib/homework";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Мой курс", robots: { index: false } };

const statusClass = {
  submitted: "bg-white/10 text-champagne",
  accepted: "bg-emerald-500/15 text-emerald-300",
  returned: "bg-orange-500/15 text-orange-300"
} as const;

export default async function CoursePage() {
  const session = await getSession();
  if (!session) redirect(loginPath("/course"));
  if (session.role !== "student" || !session.studentId) redirect("/mentor");

  const studentId = session.studentId;
  const student = await prisma.student.findUnique({ where: { id: studentId }, include: { group: true } });
  if (!student) redirect("/login");

  const [progress, homework, liveDone] = await Promise.all([
    workbookProgress([studentId]),
    prisma.homework.findMany({ where: { studentId } }),
    // Only "took part" — no scores here (see lib/live.ts, no-stress rule).
    prisma.liveSession.findMany({
      where: { groupId: student.groupId, finishedAt: { not: null }, answers: { some: { studentId } } },
      orderBy: { startedAt: "asc" },
      select: { id: true, title: true, startedAt: true }
    })
  ]);
  const percentByDay = progress.get(studentId)?.percentByDay ?? {};
  const homeworkByDay = new Map(homework.map((h) => [h.dayIndex, h]));

  const now = new Date();
  const days = courseDaysList.map((day) => ({ day, start: lessonStart(student.group, day) }));
  const nextLesson = days.find(({ start }) => start && start.getTime() > now.getTime() - 3 * 60 * 60 * 1000);

  return (
    <div className="min-h-[100dvh] bg-navy-950 text-white">
      <AppHeader title={`PrimeTeens · ${student.group.name}`} logout />
      <LiveBanner />
      <main className="mx-auto max-w-3xl px-4 pb-16 pt-6">
        <h1 className="font-display text-2xl font-semibold">Привет, {student.shortName ?? student.fullName}!</h1>
        <p className="mt-2 text-sm text-muted">
          Здесь тетрадь по дням курса и домашка. Всё сохраняется само — можно продолжать с телефона или компьютера.
        </p>

        {student.group.archivedAt ? (
          <p className="mt-5 rounded-lg border border-white/10 bg-navy-900 px-4 py-3 text-sm text-muted">
            Поток завершён — тетрадь и домашка доступны только для чтения.
          </p>
        ) : (
          nextLesson?.start && (
            <Link
              href={`/course/day/${nextLesson.day.index}`}
              className="mt-5 block rounded-xl border border-gold-500/40 bg-navy-900 px-4 py-3 hover:border-gold-400"
            >
              <div className="text-xs font-semibold uppercase tracking-wide text-gold-400">
                {sameCourseDate(nextLesson.start, now) ? "Сегодня" : "Следующее занятие"}
              </div>
              <div className="mt-1 font-semibold">
                День {nextLesson.day.index} · {nextLesson.day.title}
              </div>
              <div className="text-sm text-muted">{formatLesson(nextLesson.start)}</div>
            </Link>
          )
        )}

        <Link
          href="/course/calendar"
          className="mt-3 flex items-center justify-between rounded-xl border border-white/10 bg-navy-900 px-4 py-3 text-sm hover:border-gold-400"
        >
          <span>Календарь: занятия, сроки домашки и мои дедлайны</span>
          <span className="text-muted">→</span>
        </Link>

        <ol className="mt-6 space-y-3">
          {days.map(({ day, start }) => {
            const hasWorkbook = workbookDays.includes(day.index);
            const pct = percentByDay[day.index] ?? 0;
            const hw = homeworkByDay.get(day.index);
            const hwStatus = hw && isHomeworkStatus(hw.status) ? hw.status : null;
            const isToday = !!start && sameCourseDate(start, now);
            return (
              <li key={day.index}>
                <Link
                  href={`/course/day/${day.index}`}
                  className={`block rounded-xl border bg-navy-900 px-4 py-3 transition hover:border-gold-400 ${
                    isToday ? "border-gold-500/60" : "border-white/10"
                  }`}
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-xs font-semibold uppercase tracking-wide text-muted">День {day.index}</span>
                    {start && <span className="text-xs text-muted">{formatLesson(start)}</span>}
                  </div>
                  <div className="mt-1 font-semibold text-porcelain">{day.title}</div>
                  {day.tasks.length > 0 && <div className="mt-1 text-sm text-muted">{day.tasks.join(" · ")}</div>}
                  <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
                    {hasWorkbook && (
                      <span className="flex items-center gap-2 text-muted">
                        Тетрадь
                        <span className="inline-block h-1.5 w-20 overflow-hidden rounded-full bg-white/10">
                          <span className="block h-full rounded-full bg-gold-500" style={{ width: `${pct}%` }} />
                        </span>
                        {pct}%
                      </span>
                    )}
                    {day.homework && (
                      <span
                        className={`rounded-full px-2 py-0.5 ${hwStatus ? statusClass[hwStatus] : "bg-white/5 text-muted"}`}
                      >
                        Домашка: {hwStatus ? homeworkStatusLabel[hwStatus] : "не сдана"}
                      </span>
                    )}
                  </div>
                </Link>
              </li>
            );
          })}
        </ol>

        {liveDone.length > 0 && (
          <section className="mt-8">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">Live на занятиях</h2>
            <ul className="mt-2 space-y-1 text-sm">
              {liveDone.map((s) => (
                <li key={s.id} className="flex justify-between gap-3">
                  <span className="text-porcelain">
                    <span className="text-emerald-300">✓</span> {s.title}
                  </span>
                  <span className="text-muted">
                    выполнено · {s.startedAt.toLocaleDateString("ru-RU", { timeZone: COURSE_TZ, day: "2-digit", month: "2-digit" })}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <p className="mt-8 text-center text-sm">
          <Link href="/workbook" className="text-muted underline hover:text-champagne">
            Открыть всю тетрадь целиком
          </Link>
        </p>
      </main>
    </div>
  );
}
