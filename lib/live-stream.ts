import { subscribeLiveGroup, type LiveNotification } from "@/lib/realtime";

// Same shape as the workbook streams (app/api/mentor/groups/[groupId]/stream):
// named "hello"/"ping" events so a client can tell a live stream from one a
// proxy is buffering, and fall back to polling.
const HEARTBEAT_MS = 10_000;

function sseFrame(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

/** SSE of a group's live-mode events; students skip "answer" (they only need state changes). */
export function liveStreamResponse(request: Request, groupId: number, opts: { answers: boolean }): Response {
  const encoder = new TextEncoder();
  let unsubscribe: (() => void) | null = null;
  let heartbeat: ReturnType<typeof setInterval> | null = null;
  const stop = () => {
    unsubscribe?.();
    if (heartbeat) clearInterval(heartbeat);
  };

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (event: string, data: unknown) => {
        try {
          controller.enqueue(encoder.encode(sseFrame(event, data)));
        } catch {
          // controller already closed
        }
      };
      unsubscribe = await subscribeLiveGroup(groupId, (msg: LiveNotification) => {
        if (msg.kind === "answer" && !opts.answers) return;
        send(msg.kind, msg);
      });
      send("hello", { groupId });
      heartbeat = setInterval(() => send("ping", { t: Date.now() }), HEARTBEAT_MS);
    },
    cancel: stop
  });
  request.signal.addEventListener("abort", stop);

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no"
    }
  });
}
