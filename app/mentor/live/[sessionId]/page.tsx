import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canRunLive } from "@/lib/auth/authorize";
import { loginPath } from "@/lib/auth/next-path";
import { AppHeader } from "@/components/app/app-header";
import { SummaryView } from "@/components/live/summary-view";
import { COURSE_TZ } from "@/lib/course";
import { sessionQuestions, summarize, type LiveQuestionData } from "@/lib/live";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Итоги live", robots: { index: false } };

function answerLabel(q: LiveQuestionData, value: unknown): string {
  if (q.kind === "choice" && typeof value === "number") return q.options[value] ?? "—";
  return String(value);
}

/** Per-student answers of one session — for the group's mentors only, never shown to students. */
export default async function LiveResultsPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const raw = (await params).sessionId;
  const id = Number(raw);
  if (!Number.isInteger(id)) notFound();

  const session = await getSession();
  if (!session) redirect(loginPath(`/mentor/live/${raw}`));
  if (session.role === "student") redirect("/course");

  const live = await prisma.liveSession.findUnique({
    where: { id },
    include: { group: { select: { name: true } }, answers: true }
  });
  if (!live || !(await canRunLive(session, live.groupId))) notFound();

  const questions = sessionQuestions(live.questions);
  const students = await prisma.student.findMany({
    where: { groupId: live.groupId, active: true },
    orderBy: { fullName: "asc" },
    select: { id: true, fullName: true }
  });
  const byKey = new Map(live.answers.map((a) => [`${a.studentId}:${a.questionIndex}`, a]));
  const quizCount = questions.filter((q) => q.kind === "choice" && q.correctIndex !== null).length;

  return (
    <div className="min-h-[100dvh] bg-navy-950 text-white">
      <AppHeader title={`Итоги · ${live.title}`} backHref="/mentor/live" backLabel="Live" logout />
      <main className="mx-auto max-w-5xl px-4 pb-16 pt-6">
        <h1 className="font-display text-xl font-semibold">{live.title}</h1>
        <p className="mt-1 text-sm text-muted">
          {live.group.name} ·{" "}
          {live.startedAt.toLocaleString("ru-RU", { timeZone: COURSE_TZ, day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
          {!live.finishedAt && (
            <>
              {" · "}
              <Link href={`/live/${live.id}`} className="text-gold-400 underline">
                ещё идёт — к экрану
              </Link>
            </>
          )}
        </p>
        <p className="mt-2 text-xs text-muted">Ученики видят только «выполнено» — ответы и баллы здесь только для наставников.</p>

        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-white/10 text-left text-muted">
                <th className="py-2 pr-4">Ученик</th>
                {questions.map((q, i) => (
                  <th key={i} className="max-w-[12rem] px-2 py-2 font-normal" title={q.prompt}>
                    <span className="line-clamp-2">
                      {i + 1}. {q.prompt}
                    </span>
                  </th>
                ))}
                {quizCount > 0 && <th className="px-2 py-2 text-right">Верно</th>}
              </tr>
            </thead>
            <tbody>
              {students.map((s) => {
                const correct = questions.filter((_, i) => byKey.get(`${s.id}:${i}`)?.correct === true).length;
                return (
                  <tr key={s.id} className="border-b border-white/5 align-top">
                    <td className="py-2 pr-4">{s.fullName}</td>
                    {questions.map((q, i) => {
                      const a = byKey.get(`${s.id}:${i}`);
                      return (
                        <td key={i} className="px-2 py-2">
                          {a ? (
                            <span className={a.correct === true ? "text-emerald-300" : a.correct === false ? "text-orange-300" : ""}>
                              {answerLabel(q, a.value)}
                            </span>
                          ) : (
                            <span className="text-white/25">—</span>
                          )}
                        </td>
                      );
                    })}
                    {quizCount > 0 && (
                      <td className="px-2 py-2 text-right text-muted">
                        {correct} из {quizCount}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <h2 className="mt-10 font-display text-lg font-semibold">Как было на экране</h2>
        <div className="mt-4 grid gap-6 sm:grid-cols-2">
          {questions.map((q, i) => (
            <div key={i} className="rounded-xl border border-white/10 bg-navy-900 p-4">
              <p className="mb-3 text-sm font-semibold">
                {i + 1}. {q.prompt}
              </p>
              <SummaryView question={q} summary={summarize(q, live.answers.filter((a) => a.questionIndex === i).map((a) => a.value))} />
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
