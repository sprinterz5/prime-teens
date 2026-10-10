import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { visibleGroupIds } from "@/lib/auth/authorize";
import { loginPath } from "@/lib/auth/next-path";
import { AppHeader } from "@/components/app/app-header";
import { courseDaysList, lessonStart } from "@/lib/course";
import { LaunchForm } from "./launch-form";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Live на уроке", robots: { index: false } };

const LESSON_TAIL_MS = 4 * 60 * 60 * 1000;

export default async function MentorLivePage() {
  const session = await getSession();
  if (!session) redirect(loginPath("/mentor/live"));
  if (session.role === "student") redirect("/course");

  const visible = await visibleGroupIds(session);
  const groups = await prisma.group.findMany({
    where: { archivedAt: null, ...(visible === "all" ? {} : { id: { in: visible } }) },
    orderBy: { name: "asc" },
    select: { id: true, name: true, startDate: true, lessonTime: true, shift: true }
  });
  const [activities, sessions] = await Promise.all([
    prisma.liveActivity.findMany({
      where: { archivedAt: null, questions: { some: {} } },
      orderBy: [{ dayIndex: "asc" }, { title: "asc" }],
      select: { id: true, title: true, dayIndex: true }
    }),
    prisma.liveSession.findMany({
      where: visible === "all" ? {} : { groupId: { in: visible } },
      orderBy: { startedAt: "desc" },
      take: 30,
      include: { group: { select: { name: true } }, _count: { select: { answers: true } } }
    })
  ]);

  // The day being taught now or next, per group: its templates go on top.
  const now = Date.now();
  const suggestedDay: Record<number, number | null> = {};
  for (const g of groups) {
    const day = courseDaysList.find((d) => {
      const start = lessonStart(g, d);
      return start && start.getTime() + LESSON_TAIL_MS > now;
    });
    suggestedDay[g.id] = day?.index ?? null;
  }

  return (
    <div className="min-h-[100dvh] bg-navy-950 text-white">
      <AppHeader title="Live на уроке" backHref="/mentor" backLabel="Кабинет" logout />
      <main className="mx-auto max-w-3xl px-4 pb-16 pt-6">
        <h1 className="font-display text-2xl font-semibold">Запустить live</h1>
        <p className="mt-2 text-sm text-muted">
          Откройте экран ведущего на проекторе. Ученики заходят с телефона на платформу — у них появится баннер «Идёт
          live». На экране только общие итоги, без имён; ответы по ученикам видите только вы.
        </p>

        {groups.length === 0 || activities.length === 0 ? (
          <p className="mt-6 text-sm text-muted">
            {groups.length === 0 ? "Нет активных групп." : "Шаблонов пока нет — их создаёт курс-директор в Студии."}
          </p>
        ) : (
          <LaunchForm groups={groups.map((g) => ({ id: g.id, name: g.name }))} activities={activities} suggestedDay={suggestedDay} />
        )}

        <h2 className="mt-10 font-display text-lg font-semibold">Проведённые</h2>
        {sessions.length === 0 ? (
          <p className="mt-2 text-sm text-muted">Пока ничего.</p>
        ) : (
          <ul className="mt-3 divide-y divide-white/5 text-sm">
            {sessions.map((s) => (
              <li key={s.id} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
                <span>
                  <span className="text-porcelain">{s.title}</span>
                  <span className="text-muted"> · {s.group.name}</span>
                </span>
                <span className="flex gap-3 text-xs text-muted">
                  {s.startedAt.toLocaleString("ru-RU", { timeZone: "Asia/Almaty", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                  {s.finishedAt ? (
                    <Link href={`/mentor/live/${s.id}`} className="text-champagne underline">
                      Итоги
                    </Link>
                  ) : (
                    <Link href={`/live/${s.id}`} className="text-gold-400 underline">
                      Идёт — к экрану
                    </Link>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
