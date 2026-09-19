import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { forbidden, unauthorized } from "@/lib/auth/authorize";
import { notifyGroupArchiveChanged } from "@/lib/realtime";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * «Вернуть в работу» — clears archivedAt and sets archiveReopened=true, so
 * the bot's archive-lock job (bot/app/scheduler.py) leaves this group alone
 * even though its course dates are still in the past. Drawings stay WebP —
 * not reconverted back to PNG; a NEW drawing save (from
 * app/api/workbook/[studentId]/drawings/[fieldId]/route.ts) writes a fresh
 * .png and removes the stale .webp for that one field, see that route.
 */
export async function POST(_request: Request, { params }: { params: Promise<{ groupId: string }> }) {
  const session = await getSession();
  if (!session) return unauthorized();
  if (session.role !== "admin") return forbidden();

  const groupId = Number((await params).groupId);
  if (!Number.isInteger(groupId)) {
    return NextResponse.json({ ok: false, message: "Некорректный groupId" }, { status: 400 });
  }

  const group = await prisma.group.findUnique({ where: { id: groupId } });
  if (!group) {
    return NextResponse.json({ ok: false, message: "Группа не найдена" }, { status: 404 });
  }
  if (!group.archivedAt) {
    return NextResponse.json({ ok: true, alreadyActive: true });
  }

  await prisma.group.update({ where: { id: groupId }, data: { archivedAt: null, archiveReopened: true } });

  const students = await prisma.student.findMany({ where: { groupId }, select: { id: true } });
  await notifyGroupArchiveChanged(
    groupId,
    students.map((s) => s.id),
    false,
    new Date().toISOString()
  );

  return NextResponse.json({ ok: true });
}
