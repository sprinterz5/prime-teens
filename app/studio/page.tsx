import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canEditLive } from "@/lib/auth/authorize";
import { loginPath } from "@/lib/auth/next-path";
import { AppHeader } from "@/components/app/app-header";
import { getCourseDay } from "@/lib/course";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Студия заданий", robots: { index: false } };

export default async function StudioPage() {
  const session = await getSession();
  if (!session) redirect(loginPath("/studio"));
  if (!canEditLive(session)) redirect(session.role === "student" ? "/course" : "/mentor");

  const activities = await prisma.liveActivity.findMany({
    where: { archivedAt: null },
    orderBy: [{ dayIndex: "asc" }, { title: "asc" }],
    include: { _count: { select: { questions: true, sessions: true } } }
  });

  return (
    <div className="min-h-[100dvh] bg-navy-950 text-white">
      <AppHeader title="Студия заданий · live-режим" backHref="/mentor" backLabel="Кабинет" logout />
      <main className="mx-auto max-w-3xl px-4 pb-16 pt-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="font-display text-2xl font-semibold">Шаблоны live-заданий</h1>
          <Link href="/studio/new" className="btn btn-primary focus-ring h-10">
            Новый шаблон
          </Link>
        </div>
        <p className="mt-2 text-sm text-muted">
          Ментор запускает шаблон на уроке, ученики отвечают с телефонов. На экране — только общие итоги, без имён.
          Правки шаблона не меняют уже проведённые сессии.
        </p>

        {activities.length === 0 ? (
          <p className="mt-8 text-sm text-muted">Шаблонов пока нет.</p>
        ) : (
          <ul className="mt-6 space-y-3">
            {activities.map((a) => {
              const day = a.dayIndex ? getCourseDay(a.dayIndex) : undefined;
              return (
                <li key={a.id}>
                  <Link
                    href={`/studio/${a.id}`}
                    className="block rounded-xl border border-white/10 bg-navy-900 px-4 py-3 hover:border-gold-400"
                  >
                    <div className="text-xs font-semibold uppercase tracking-wide text-muted">
                      {day ? `День ${day.index} · ${day.title}` : "Без дня"}
                    </div>
                    <div className="mt-1 font-semibold text-porcelain">{a.title}</div>
                    <div className="mt-1 text-xs text-muted">
                      Вопросов: {a._count.questions} · запусков: {a._count.sessions}
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </main>
    </div>
  );
}
