import { createHash } from "node:crypto";
import { prisma } from "@/lib/prisma";
import { newSessionPayload, staffRole, type SessionPayload } from "@/lib/auth/session";

/**
 * Login outside Telegram: /login in either bot writes a one-time link token
 * (stored as sha256) and a 6-digit code to login_codes — see
 * bot/app/db.py:issue_login_code. Either one is exchanged here, exactly once,
 * for an ordinary session cookie. The session carries the Telegram id the
 * code was issued to, so refreshFromDatabase keeps re-checking it against
 * the account on every request, same as Mini App sessions.
 */

export function hashLoginToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

type Lookup = { tokenHash: string } | { code: string };

export async function consumeLogin(lookup: Lookup): Promise<SessionPayload | null> {
  const now = new Date();
  const row = await prisma.loginCode.findFirst({
    where: { ...lookup, usedAt: null, expiresAt: { gt: now } },
    orderBy: { createdAt: "desc" }
  });
  if (!row) return null;

  // Claim it atomically: of two parallel requests with the same code only one wins.
  const claimed = await prisma.loginCode.updateMany({
    where: { tokenHash: row.tokenHash, usedAt: null },
    data: { usedAt: now }
  });
  if (claimed.count !== 1) return null;

  const tgUserId = String(row.tgUserId);

  if (row.role === "student" && row.studentId) {
    const student = await prisma.student.findUnique({
      where: { id: row.studentId },
      select: { active: true, tgUserId: true }
    });
    if (!student?.active || String(student.tgUserId) !== tgUserId) return null;
    return newSessionPayload({ role: "student", studentId: row.studentId, tgUserId });
  }

  if (row.role === "mentor" && row.mentorId) {
    const mentor = await prisma.mentor.findUnique({
      where: { id: row.mentorId },
      select: { isAdmin: true, isDirector: true, tgUserId: true }
    });
    if (!mentor || String(mentor.tgUserId) !== tgUserId) return null;
    return newSessionPayload({ role: staffRole(mentor), mentorId: row.mentorId, tgUserId });
  }

  return null;
}

/** Where a freshly logged-in (or already logged-in) user lands. */
export function homePath(session: Pick<SessionPayload, "role">): string {
  return session.role === "student" ? "/course" : "/mentor";
}
