import { forbidden } from "@/lib/auth/authorize";
import { currentStudent } from "@/lib/live-student";
import { liveStreamResponse } from "@/lib/live-stream";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Student's SSE: state changes of their group's live session (no per-answer events). */
export async function GET(request: Request) {
  const student = await currentStudent();
  if (!student) return forbidden();
  return liveStreamResponse(request, student.groupId, { answers: false });
}
