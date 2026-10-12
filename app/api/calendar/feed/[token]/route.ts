import { prisma } from "@/lib/prisma";
import { studentEvents, toIcs } from "@/lib/calendar";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Public .ics feed behind a secret token (see ../../subscription). Inactive students get nothing. */
export async function GET(request: Request, { params }: { params: Promise<{ token: string }> }) {
  const token = (await params).token.replace(/\.ics$/, "");
  const student = token
    ? await prisma.student.findUnique({
        where: { calendarToken: token },
        include: { group: true, deadlines: true, homework: { select: { dayIndex: true } } }
      })
    : null;
  if (!student || !student.active) return new Response("Not found", { status: 404 });

  const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL || new URL(request.url).origin).replace(/\/$/, "");
  const ics = toIcs(studentEvents(student.group, student.deadlines, new Set(student.homework.map((h) => h.dayIndex))), {
    name: `PrimeTeens · ${student.group.name}`,
    siteUrl,
    studentId: student.id
  });
  return new Response(ics, {
    headers: {
      "Content-Type": "text/calendar; charset=utf-8",
      "Cache-Control": "private, max-age=300",
      "Content-Disposition": 'inline; filename="primeteens.ics"'
    }
  });
}
