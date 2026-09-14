import { getSession } from "@/lib/auth/session";
import { canReadStudent, forbidden, unauthorized } from "@/lib/auth/authorize";
import { subscribeStudent, type WorkbookNotification } from "@/lib/realtime";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Named "hello"/"ping" events (not SSE comments) so the client can tell a live
// stream from one a proxy is silently buffering, and fall back to polling.
const HEARTBEAT_MS = 10_000;

function sseFrame(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

export async function GET(request: Request, { params }: { params: Promise<{ studentId: string }> }) {
  const session = await getSession();
  if (!session) return unauthorized();

  const studentId = Number((await params).studentId);
  if (!Number.isInteger(studentId)) {
    return new Response("Некорректный studentId", { status: 400 });
  }
  if (!(await canReadStudent(session, studentId))) return forbidden();

  const encoder = new TextEncoder();
  let unsubscribe: (() => void) | null = null;
  let heartbeat: ReturnType<typeof setInterval> | null = null;

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const onMessage = (msg: WorkbookNotification) => {
        controller.enqueue(encoder.encode(sseFrame(msg.kind, msg)));
      };
      unsubscribe = await subscribeStudent(studentId, onMessage);
      controller.enqueue(encoder.encode(sseFrame("hello", { studentId })));
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
