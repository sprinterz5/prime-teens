import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { loginPath } from "@/lib/auth/next-path";
import { AppHeader } from "@/components/app/app-header";
import { COURSE_TZ } from "@/lib/course";
import { courseDateKey, studentEvents, type CalendarEvent } from "@/lib/calendar";
import { AddDeadline, DeleteDeadline, Subscribe } from "./calendar-actions";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Календарь", robots: { index: false } };

const kindStyle: Record<CalendarEvent["kind"], { dot: string; label: string }> = {
  lesson: { dot: "bg-gold-500", label: "Занятие" },
  homework: { dot: "bg-sky-400", label: "Домашка" },
  deadline: { dot: "bg-emerald-400", label: "Мой дедлайн" }
};

function dayHeading(key: string, todayKey: string): string {
  const [y, m, d] = key.split("-").map(Number);
  const label = new Date(Date.UTC(y, m - 1, d, 12)).toLocaleDateString("ru-RU", {
    timeZone: "UTC",
    weekday: "long",
    day: "numeric",
    month: "long"
  });
  return key === todayKey ? `Сегодня · ${label}` : label;
}

function time(e: CalendarEvent): string {
  if (e.allDay) return "весь день";
  const fmt = (d: Date) => d.toLocaleTimeString("ru-RU", { timeZone: COURSE_TZ, hour: "2-digit", minute: "2-digit" });
  return e.end ? `${fmt(e.start)}–${fmt(e.end)}` : `до ${fmt(e.start)}`;
}

function DayList({ days, todayKey }: { days: [string, CalendarEvent[]][]; todayKey: string }) {
  return (
    <ol className="space-y-5">
      {days.map(([key, events]) => (
        <li key={key}>
          <h2 className={`text-xs font-semibold uppercase tracking-wide ${key === todayKey ? "text-gold-400" : "text-muted"}`}>
            {dayHeading(key, todayKey)}
          </h2>
          <ul className="mt-2 space-y-2">
            {events.map((e) => {
              const style = kindStyle[e.kind];
              const body = (
                <>
                  <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
                  <span className="min-w-0 flex-1">
                    <span className={`block ${e.done ? "text-muted" : "text-porcelain"}`}>{e.title}</span>
                    <span className="text-xs text-muted">
                      {style.label} · {time(e)}
                    </span>
                  </span>
                </>
              );
              return (
                <li key={e.uid} className="flex items-start gap-3 rounded-xl border border-white/10 bg-navy-900 px-4 py-3 text-sm">
                  {e.href ? (
                    <Link href={e.href} className="flex min-w-0 flex-1 items-start gap-3 hover:text-champagne">
                      {body}
                    </Link>
                  ) : (
                    <span className="flex min-w-0 flex-1 items-start gap-3">{body}</span>
                  )}
                  {e.deadlineId && <DeleteDeadline id={e.deadlineId} />}
                </li>
              );
            })}
          </ul>
        </li>
      ))}
    </ol>
  );
}

export default async function CalendarPage() {
  const session = await getSession();
  if (!session) redirect(loginPath("/course/calendar"));
  if (session.role !== "student" || !session.studentId) redirect("/mentor");

  const student = await prisma.student.findUnique({
    where: { id: session.studentId },
    include: { group: true, deadlines: true, homework: { select: { dayIndex: true } } }
  });
  if (!student) redirect("/login");

  const now = new Date();
  const todayKey = courseDateKey(now);
  const byDay = new Map<string, CalendarEvent[]>();
  for (const e of studentEvents(student.group, student.deadlines, new Set(student.homework.map((h) => h.dayIndex)))) {
    const key = courseDateKey(e.start);
    byDay.set(key, [...(byDay.get(key) ?? []), e]);
  }
  const days = [...byDay.entries()];
  const upcoming = days.filter(([key]) => key >= todayKey);
  const past = days.filter(([key]) => key < todayKey).reverse();

  return (
    <div className="min-h-[100dvh] bg-navy-950 text-white">
      <AppHeader title="Календарь" backHref="/course" backLabel="Мой курс" logout />
      <main className="mx-auto max-w-2xl px-4 pb-16 pt-6">
        <h1 className="font-display text-2xl font-semibold">Календарь</h1>
        <p className="mt-2 text-sm text-muted">
          Занятия и сроки домашки ставятся сами. Добавь свои дедлайны — олимпиады, летние программы, конкурсы.
        </p>

        <AddDeadline />
        <Subscribe />

        <section className="mt-8">
          {upcoming.length ? <DayList days={upcoming} todayKey={todayKey} /> : <p className="text-sm text-muted">Впереди пока ничего.</p>}
        </section>

        {past.length > 0 && (
          <details className="mt-8">
            <summary className="cursor-pointer text-sm text-muted">Прошедшие ({past.reduce((n, [, e]) => n + e.length, 0)})</summary>
            <div className="mt-4 opacity-70">
              <DayList days={past} todayKey={todayKey} />
            </div>
          </details>
        )}
      </main>
    </div>
  );
}
