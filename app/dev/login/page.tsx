import { notFound } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { DevLoginButton } from "./dev-login-button";

export const dynamic = "force-dynamic";

function devLoginEnabled(): boolean {
  return process.env.NODE_ENV !== "production" && process.env.DEV_LOGIN === "1";
}

export default async function DevLoginPage() {
  if (!devLoginEnabled()) notFound();

  const [students, mentors] = await Promise.all([
    prisma.student.findMany({ include: { group: true }, orderBy: { fullName: "asc" } }),
    prisma.mentor.findMany({ orderBy: { id: "asc" } })
  ]);

  return (
    <main className="mx-auto max-w-2xl px-6 py-16 text-white">
      <h1 className="font-display text-2xl font-semibold">Dev-логин</h1>
      <p className="mt-2 text-sm text-white/60">
        Только для разработки (NODE_ENV≠production и DEV_LOGIN=1). Задаёт cookie сессии без Telegram.
      </p>

      <h2 className="mt-8 text-lg font-semibold text-white/90">Ученики</h2>
      <div className="mt-3 flex flex-wrap gap-3">
        {students.map((s) => (
          <DevLoginButton
            key={s.id}
            kind="student"
            studentId={s.id}
            redirectTo="/workbook"
            label={`${s.fullName} (${s.group.name})`}
          />
        ))}
        {students.length === 0 && <p className="text-sm text-white/50">Нет учеников — запустите pnpm db:seed</p>}
      </div>

      <h2 className="mt-8 text-lg font-semibold text-white/90">Менторы / админы</h2>
      <div className="mt-3 flex flex-wrap gap-3">
        {mentors.map((m) => (
          <DevLoginButton
            key={m.id}
            kind="mentor"
            mentorId={m.id}
            redirectTo="/mentor"
            label={`${m.fullName ?? "Без имени"} ${m.isAdmin ? "(админ)" : "(ментор)"}`}
          />
        ))}
        {mentors.length === 0 && <p className="text-sm text-white/50">Нет менторов — запустите pnpm db:seed</p>}
      </div>
    </main>
  );
}
