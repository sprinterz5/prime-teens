import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canEditLive, forbidden, unauthorized } from "@/lib/auth/authorize";
import { activityInputSchema, firstIssue, type LiveKind } from "@/lib/live";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string }> };

async function editorGuard(params: Params["params"]) {
  const session = await getSession();
  if (!session) return { error: unauthorized() };
  if (!canEditLive(session)) return { error: forbidden() };
  const id = Number((await params).id);
  if (!Number.isInteger(id)) return { error: NextResponse.json({ ok: false, message: "Некорректный id" }, { status: 400 }) };
  return { id };
}

export async function GET(_request: Request, { params }: Params) {
  const guard = await editorGuard(params);
  if ("error" in guard) return guard.error;

  const activity = await prisma.liveActivity.findFirst({
    where: { id: guard.id, archivedAt: null },
    include: { questions: { orderBy: { position: "asc" } } }
  });
  if (!activity) return NextResponse.json({ ok: false, message: "Шаблон не найден" }, { status: 404 });

  return NextResponse.json({
    id: activity.id,
    title: activity.title,
    dayIndex: activity.dayIndex,
    questions: activity.questions.map((q) => ({
      kind: q.kind as LiveKind,
      prompt: q.prompt,
      options: Array.isArray(q.options) ? q.options : [],
      correctIndex: q.correctIndex,
      timeLimitSec: q.timeLimitSec
    }))
  });
}

/**
 * Replaces the template's questions wholesale. Sessions already run keep
 * their own snapshot (live_sessions.questions), so this never changes results.
 */
export async function PUT(request: Request, { params }: Params) {
  const guard = await editorGuard(params);
  if ("error" in guard) return guard.error;

  const parsed = activityInputSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ ok: false, message: firstIssue(parsed.error) }, { status: 400 });
  const { title, dayIndex, questions } = parsed.data;

  const exists = await prisma.liveActivity.findFirst({ where: { id: guard.id, archivedAt: null }, select: { id: true } });
  if (!exists) return NextResponse.json({ ok: false, message: "Шаблон не найден" }, { status: 404 });

  await prisma.$transaction([
    prisma.liveQuestion.deleteMany({ where: { activityId: guard.id } }),
    prisma.liveActivity.update({
      where: { id: guard.id },
      data: { title, dayIndex, questions: { create: questions.map((q, position) => ({ ...q, position })) } }
    })
  ]);
  return NextResponse.json({ ok: true, id: guard.id });
}

/** Archive, not delete: past sessions still point at the template. */
export async function DELETE(_request: Request, { params }: Params) {
  const guard = await editorGuard(params);
  if ("error" in guard) return guard.error;
  await prisma.liveActivity.updateMany({ where: { id: guard.id, archivedAt: null }, data: { archivedAt: new Date() } });
  return NextResponse.json({ ok: true });
}
