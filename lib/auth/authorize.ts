import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession, verifyPrintToken, type SessionPayload } from "@/lib/auth/session";

export function unauthorized(message = "Не авторизовано") {
  return NextResponse.json({ ok: false, message }, { status: 401 });
}

export function forbidden(message = "Доступ запрещён") {
  return NextResponse.json({ ok: false, message }, { status: 403 });
}

/** Admin and course director: every group, every live template. */
export function seesAllGroups(session: SessionPayload): boolean {
  return session.role === "admin" || session.role === "director";
}

/** Who creates and edits live-mode templates (/studio). */
export function canEditLive(session: SessionPayload): boolean {
  return seesAllGroups(session);
}

/** Group ids a mentor/director/admin session may see. Admin and director see every group. */
export async function visibleGroupIds(session: SessionPayload): Promise<number[] | "all"> {
  if (seesAllGroups(session)) return "all";
  if (session.role === "mentor" && session.mentorId) {
    const rows = await prisma.mentorGroup.findMany({
      where: { mentorId: session.mentorId },
      select: { groupId: true }
    });
    return rows.map((r) => r.groupId);
  }
  return [];
}

/** Whether the session may READ a given student's workbook. */
export async function canReadStudent(session: SessionPayload, studentId: number): Promise<boolean> {
  if (session.role === "student") return session.studentId === studentId;
  if (seesAllGroups(session)) return true;
  if (session.role === "mentor" && session.mentorId) {
    const student = await prisma.student.findUnique({ where: { id: studentId }, select: { groupId: true } });
    if (!student) return false;
    const link = await prisma.mentorGroup.findUnique({
      where: { mentorId_groupId: { mentorId: session.mentorId, groupId: student.groupId } }
    });
    return !!link;
  }
  return false;
}

/** Whether the session may WRITE (PUT) a given student's workbook — students only, own record. */
export function canWriteStudent(session: SessionPayload, studentId: number): boolean {
  return session.role === "student" && session.studentId === studentId;
}

/** All student ids visible to a mentor/admin session, optionally scoped to one group. */
export async function visibleStudentIds(session: SessionPayload, groupId?: number): Promise<number[]> {
  const groups = await visibleGroupIds(session);
  if (groups !== "all") {
    if (groups.length === 0) return [];
    if (groupId !== undefined && !groups.includes(groupId)) return [];
  }
  const where = groupId !== undefined ? { groupId } : groups === "all" ? {} : { groupId: { in: groups } };
  const students = await prisma.student.findMany({ where, select: { id: true } });
  return students.map((s) => s.id);
}

export async function canAccessGroup(session: SessionPayload, groupId: number): Promise<boolean> {
  const groups = await visibleGroupIds(session);
  return groups === "all" || groups.includes(groupId);
}

/** Who may start and drive a live session in a group: its mentors, directors, admins. */
export async function canRunLive(session: SessionPayload, groupId: number): Promise<boolean> {
  return session.role !== "student" && (await canAccessGroup(session, groupId));
}

export type ReadAuthResult = { ok: true } | { ok: false; status: 401 | 403 };

/**
 * Authorizes a read of one student's workbook data (entries/drawings/stream
 * GET routes) either by a live session (student themself, or a mentor/admin
 * with access — same rule as canReadStudent) OR a short-lived print token
 * scoped to exactly this studentId (?token=..., see
 * lib/auth/session.ts:verifyPrintToken). The token path exists because
 * /workbook/print (see app/workbook/print/route.ts) is rendered by a
 * headless Playwright context during PDF export (scripts/archive-group.ts),
 * which has no session cookie — the print route forwards its own token to
 * the client (window.__WB__.token), which appends it to these same API
 * calls (see PLATFORM_JS in workbook/src/build_web.py).
 */
export async function authorizeStudentRead(request: Request, studentId: number): Promise<ReadAuthResult> {
  const session = await getSession();
  if (session) {
    return (await canReadStudent(session, studentId)) ? { ok: true } : { ok: false, status: 403 };
  }
  const token = new URL(request.url).searchParams.get("token");
  return verifyPrintToken(token, studentId) ? { ok: true } : { ok: false, status: 401 };
}
