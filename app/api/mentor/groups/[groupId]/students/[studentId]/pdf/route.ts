import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canAccessGroup, forbidden, unauthorized } from "@/lib/auth/authorize";
import { studentPdfRelPath } from "@/lib/workbook/archive";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Serves a student's archived-workbook PDF (storage/archive/<groupId>/...),
 * produced by scripts/archive-group.ts / scripts/archive-pending.ts. Any
 * mentor/admin with access to the group can download it — same rule as the
 * rest of the mentor API (canAccessGroup), students can't reach this route
 * at all (session.role === "student" is rejected by canAccessGroup's callers
 * implicitly via visibleGroupIds, which only handles admin/mentor).
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ groupId: string; studentId: string }> }
) {
  const session = await getSession();
  if (!session) return unauthorized();
  if (session.role === "student") return forbidden();

  const { groupId: groupIdRaw, studentId: studentIdRaw } = await params;
  const groupId = Number(groupIdRaw);
  const studentId = Number(studentIdRaw);
  if (!Number.isInteger(groupId) || !Number.isInteger(studentId)) {
    return NextResponse.json({ ok: false, message: "Некорректные параметры" }, { status: 400 });
  }
  if (!(await canAccessGroup(session, groupId))) return forbidden();

  const student = await prisma.student.findUnique({ where: { id: studentId }, select: { fullName: true, groupId: true } });
  if (!student || student.groupId !== groupId) {
    return NextResponse.json({ ok: false, message: "Студент не найден в этой группе" }, { status: 404 });
  }

  const rel = studentPdfRelPath(groupId, studentId, student.fullName);
  try {
    const buf = await readFile(path.join(process.cwd(), rel));
    // HTTP header values are ByteString-only — the Cyrillic filename can't go
    // straight into Content-Disposition (throws on Cyrillic characters), so
    // an ASCII fallback plus the RFC 5987/6266 filename* form is used
    // instead of the raw name.
    const encodedName = encodeURIComponent(path.basename(rel));
    return new NextResponse(new Uint8Array(buf), {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": `attachment; filename="student-${studentId}.pdf"; filename*=UTF-8''${encodedName}`,
        "Cache-Control": "private, no-store"
      }
    });
  } catch {
    return NextResponse.json({ ok: false, message: "PDF ещё не готов" }, { status: 404 });
  }
}
