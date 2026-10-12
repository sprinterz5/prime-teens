import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canRunLive, forbidden, unauthorized } from "@/lib/auth/authorize";
import { notifyLive } from "@/lib/realtime";
import { sessionQuestions } from "@/lib/live";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * The presenter drives the session: { action, from }.
 *   next   — lobby → first question open; reveal → next question open (or finished after the last)
 *   reveal — open question → show aggregates (also sent by the screen when the timer runs out)
 *   finish — end the session at any point
 * `from` is the question index the presenter is looking at: a stale or
 * double click (two tabs, timer and button at once) changes nothing.
 */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session) return unauthorized();
  const id = Number((await params).id);
  const live = Number.isInteger(id) ? await prisma.liveSession.findUnique({ where: { id } }) : null;
  if (!live) return NextResponse.json({ ok: false, message: "Сессия не найдена" }, { status: 404 });
  if (!(await canRunLive(session, live.groupId))) return forbidden();

  const body = await request.json().catch(() => null);
  const action = body?.action;
  const from = Number(body?.from);
  if (live.finishedAt) return NextResponse.json({ ok: true, changed: false });
  if (action !== "finish" && from !== live.currentIndex) return NextResponse.json({ ok: true, changed: false });

  const total = sessionQuestions(live.questions).length;
  const now = new Date();
  let data: { phase: string; currentIndex?: number; openedAt?: Date; finishedAt?: Date } | null = null;

  if (action === "finish") {
    data = { phase: "finished", finishedAt: now };
  } else if (action === "reveal" && live.phase === "open") {
    data = { phase: "reveal" };
  } else if (action === "next" && (live.phase === "lobby" || live.phase === "reveal")) {
    const nextIndex = live.currentIndex + 1;
    data = nextIndex < total ? { phase: "open", currentIndex: nextIndex, openedAt: now } : { phase: "finished", finishedAt: now };
  }
  if (!data) return NextResponse.json({ ok: true, changed: false });

  // Conditional on the state we read, so two racing requests apply once.
  const updated = await prisma.liveSession.updateMany({
    where: { id, phase: live.phase, currentIndex: live.currentIndex, finishedAt: null },
    data
  });
  if (updated.count > 0) await notifyLive({ kind: "state", sessionId: id, groupId: live.groupId });
  return NextResponse.json({ ok: true, changed: updated.count > 0 });
}
