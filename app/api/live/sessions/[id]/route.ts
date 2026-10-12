import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canRunLive, forbidden, unauthorized } from "@/lib/auth/authorize";
import { presenterState } from "@/lib/live-state";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Presenter screen state: current question, timer, answered count, aggregates at reveal. */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session) return unauthorized();
  const id = Number((await params).id);
  const live = Number.isInteger(id)
    ? await prisma.liveSession.findUnique({ where: { id }, select: { groupId: true } })
    : null;
  if (!live) return NextResponse.json({ ok: false, message: "Сессия не найдена" }, { status: 404 });
  if (!(await canRunLive(session, live.groupId))) return forbidden();

  return NextResponse.json(await presenterState(id));
}
