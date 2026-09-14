import { notFound } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canReadStudent } from "@/lib/auth/authorize";
import { AppHeader } from "@/components/app/app-header";
import { TelegramViewport } from "@/components/app/telegram-viewport";

export const dynamic = "force-dynamic";

export default async function MentorStudentWorkbookPage({
  params
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId: studentIdRaw } = await params;
  const studentId = Number(studentIdRaw);
  const session = await getSession();

  if (!session || session.role === "student") {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-navy-950 px-6 text-center text-white">
        <h1 className="font-display text-xl font-semibold">Только для менторов и админов</h1>
      </main>
    );
  }

  if (!Number.isInteger(studentId)) notFound();
  if (!(await canReadStudent(session, studentId))) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-navy-950 px-6 text-center text-white">
        <h1 className="font-display text-xl font-semibold">Доступ запрещён</h1>
        <p className="text-sm text-muted">Этот ученик не в ваших группах.</p>
      </main>
    );
  }

  const student = await prisma.student.findUnique({ where: { id: studentId }, include: { group: true } });
  if (!student) notFound();

  return (
    <div className="flex h-[100dvh] flex-col bg-navy-950">
      <TelegramViewport />
      <AppHeader
        title={`${student.fullName} · ${student.group.name}`}
        backHref="/mentor"
        backLabel="К списку группы"
      />
      <iframe
        src={`/workbook/frame?studentId=${student.id}`}
        title="Рабочая тетрадь (просмотр)"
        className="h-full w-full border-0"
      />
    </div>
  );
}
