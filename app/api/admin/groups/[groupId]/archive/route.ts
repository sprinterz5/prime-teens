import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { forbidden, unauthorized } from "@/lib/auth/authorize";
import { notifyGroupArchiveChanged } from "@/lib/realtime";
import { convertGroupDrawingsToWebp } from "@/lib/workbook/archive";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * «Завершить поток» — admin button (app/mentor/mentor-dashboard.tsx). Sets
 * archivedAt immediately (workbook writes start refusing right away, see
 * lib/workbook/archive.ts + the two PUT routes) and runs WebP conversion of
 * this group's drawings synchronously, since that's fast (a handful of PNGs
 * per student, sharp is not slow) and the admin is waiting on the button.
 *
 * PDF export is deliberately NOT triggered here — Playwright/Chromium is
 * heavy and slow (seconds per student), and doing it inline would make this
 * button hang for a large group. It's left to `pnpm archive:pending`
 * (scripts/archive-pending.ts), which a nightly systemd timer runs — see
 * deploy/. An admin can also run `pnpm archive:group <id>` directly if they
 * want the PDFs sooner without waiting for the nightly run.
 *
 * Idempotent: re-clicking an already-archived group just re-runs the WebP
 * pass (a no-op if already converted) without moving archivedAt.
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

  const archivedAt = group.archivedAt ?? new Date();
  if (!group.archivedAt) {
    await prisma.group.update({ where: { id: groupId }, data: { archivedAt, archiveReopened: false } });

    const students = await prisma.student.findMany({ where: { groupId }, select: { id: true } });
    await notifyGroupArchiveChanged(
      groupId,
      students.map((s) => s.id),
      true,
      archivedAt.toISOString()
    );
  }

  const webp = await convertGroupDrawingsToWebp(groupId);

  return NextResponse.json({ ok: true, archivedAt: archivedAt.toISOString(), webp });
}
