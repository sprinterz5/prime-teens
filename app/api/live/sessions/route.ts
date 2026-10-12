import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canRunLive, forbidden, unauthorized } from "@/lib/auth/authorize";
import { notifyLive } from "@/lib/realtime";
import type { LiveKind, LiveQuestionData } from "@/lib/live";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Starts a template in a group: { activityId, groupId }. The questions are
 * copied into the session, so editing the template later can't change these
 * results. A group runs one session at a time — a forgotten one is finished.
 */
export async function POST(request: Request) {
  const session = await getSession();
  if (!session) return unauthorized();

  const body = await request.json().catch(() => null);
  const activityId = Number(body?.activityId);
  const groupId = Number(body?.groupId);
  if (!Number.isInteger(activityId) || !Number.isInteger(groupId)) {
    return NextResponse.json({ ok: false, message: "Некорректный запрос" }, { status: 400 });
  }
  if (!(await canRunLive(session, groupId))) return forbidden();

  const [group, activity] = await Promise.all([
    prisma.group.findUnique({ where: { id: groupId }, select: { archivedAt: true } }),
    prisma.liveActivity.findFirst({
      where: { id: activityId, archivedAt: null },
      include: { questions: { orderBy: { position: "asc" } } }
    })
  ]);
  if (!group) return NextResponse.json({ ok: false, message: "Группа не найдена" }, { status: 404 });
  if (group.archivedAt) {
    return NextResponse.json({ ok: false, message: "Поток завершён — live недоступен" }, { status: 409 });
  }
  if (!activity || activity.questions.length === 0) {
    return NextResponse.json({ ok: false, message: "Шаблон не найден или пуст" }, { status: 404 });
  }

  const snapshot: LiveQuestionData[] = activity.questions.map((q) => ({
    kind: q.kind as LiveKind,
    prompt: q.prompt,
    options: Array.isArray(q.options) ? (q.options as string[]) : [],
    correctIndex: q.correctIndex,
    timeLimitSec: q.timeLimitSec
  }));

  const now = new Date();
  const [, created] = await prisma.$transaction([
    prisma.liveSession.updateMany({
      where: { groupId, finishedAt: null },
      data: { phase: "finished", finishedAt: now }
    }),
    prisma.liveSession.create({
      data: { activityId, groupId, startedBy: session.mentorId ?? null, title: activity.title, questions: snapshot }
    })
  ]);
  await notifyLive({ kind: "state", sessionId: created.id, groupId });
  return NextResponse.json({ ok: true, id: created.id });
}
