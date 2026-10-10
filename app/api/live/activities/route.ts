import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canEditLive, forbidden, unauthorized } from "@/lib/auth/authorize";
import { activityInputSchema, firstIssue } from "@/lib/live";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Templates for launching (every staff member) and editing (/studio). */
export async function GET() {
  const session = await getSession();
  if (!session) return unauthorized();
  if (session.role === "student") return forbidden();

  const activities = await prisma.liveActivity.findMany({
    where: { archivedAt: null },
    orderBy: [{ dayIndex: "asc" }, { title: "asc" }],
    include: { _count: { select: { questions: true } } }
  });
  return NextResponse.json({
    activities: activities.map((a) => ({
      id: a.id,
      title: a.title,
      dayIndex: a.dayIndex,
      questionCount: a._count.questions,
      updatedAt: a.updatedAt.toISOString()
    }))
  });
}

export async function POST(request: Request) {
  const session = await getSession();
  if (!session) return unauthorized();
  if (!canEditLive(session)) return forbidden();

  const parsed = activityInputSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ ok: false, message: firstIssue(parsed.error) }, { status: 400 });
  const { title, dayIndex, questions } = parsed.data;

  const activity = await prisma.liveActivity.create({
    data: {
      title,
      dayIndex,
      createdBy: session.mentorId ?? null,
      questions: { create: questions.map((q, position) => ({ ...q, position })) }
    }
  });
  return NextResponse.json({ ok: true, id: activity.id });
}
