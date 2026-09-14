import { getSession } from "@/lib/auth/session";
import { canAccessGroup, forbidden, unauthorized } from "@/lib/auth/authorize";
import { subscribeGroup, type WorkbookNotification } from "@/lib/realtime";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Named "hello"/"ping" events (not SSE comments) so the client can tell a live
// stream from one a proxy is silently buffering, and fall back to polling.
const HEARTBEAT_MS = 10_000;

function sseFrame(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

export async function GET(request: Request, { params }: { params: Promise<{ groupId: string }> }) {
  const session = await getSession();
  if (!session) return unauthorized();
  if (session.role === "student") return forbidden();

  const groupId = Number((await params).groupId);
  if (!Number.isInteger(groupId)) {
    return new Response("Некорректный groupId", { status: 400 });
  }
  if (!(await canAccessGroup(session, groupId))) return forbidden();

  const encoder = new TextEncoder();
  let unsubscribe: (() => void) | null = null;
  let heartbeat: ReturnType<typeof setInterval> | null = null;

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const onMessage = (msg: WorkbookNotification) => {
        controller.enqueue(encoder.encode(sseFrame(msg.kind, msg)));
      };
      unsubscribe = await subscribeGroup(groupId, onMessage);
      controller.enqueue(encoder.encode(sseFrame("hello", { groupId })));
      heartbeat = setInterval(() => {
        try {
          controller.enqueue(encoder.encode(sseFrame("ping", { t: Date.now() })));
        } catch {
          // controller already closed
        }
      }, HEARTBEAT_MS);
    },
    cancel() {
      unsubscribe?.();
      if (heartbeat) clearInterval(heartbeat);
    }
  });

  request.signal.addEventListener("abort", () => {
    unsubscribe?.();
    if (heartbeat) clearInterval(heartbeat);
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no"
    }
  });
}
