import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canRunLive, forbidden, unauthorized } from "@/lib/auth/authorize";
import { liveStreamResponse } from "@/lib/live-stream";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Presenter's SSE: state changes and every new answer (the "ответили N из M" counter). */
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session) return unauthorized();
  const id = Number((await params).id);
  const live = Number.isInteger(id)
    ? await prisma.liveSession.findUnique({ where: { id }, select: { groupId: true } })
    : null;
  if (!live) return new Response("Сессия не найдена", { status: 404 });
  if (!(await canRunLive(session, live.groupId))) return forbidden();
  return liveStreamResponse(request, live.groupId, { answers: true });
}
