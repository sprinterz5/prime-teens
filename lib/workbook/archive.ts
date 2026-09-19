import { NextResponse } from "next/server";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import sharp from "sharp";
import { prisma } from "@/lib/prisma";

export const ARCHIVE_LOCK_MESSAGE = "Поток завершён — тетрадь доступна только для чтения";

export type StudentGroupInfo = { groupId: number; archivedAt: Date | null };

/**
 * Student -> their group's id + archive state, in one query. Used by both
 * write routes (entries, drawings) so they don't run two separate lookups
 * (one for groupId, one for "is this archived") — and by the workbook frame
 * route to decide edit vs readonly mode for a student session.
 */
export async function getStudentGroupInfo(studentId: number): Promise<StudentGroupInfo | null> {
  const student = await prisma.student.findUnique({
    where: { id: studentId },
    select: { group: { select: { id: true, archivedAt: true } } }
  });
  if (!student) return null;
  return { groupId: student.group.id, archivedAt: student.group.archivedAt };
}

/** 409 refusal for a write against an archived group's workbook. */
export function archivedResponse() {
  return NextResponse.json({ ok: false, message: ARCHIVE_LOCK_MESSAGE }, { status: 409 });
}

// ---------------------------------------------------------------------------
// WebP compression (step 3 of the archive feature): once a group is
// archived, its drawings are re-encoded from PNG to lossy WebP to shrink
// storage/drawings — the tetrad is read-only from then on, so the raster
// never needs another lossless edit pass.
// ---------------------------------------------------------------------------

const WEBP_QUALITY = 80;
const WEBP_ALPHA_QUALITY = 100; // canvases can have transparent background — keep alpha crisp

export type WebpConversionResult = {
  converted: number;
  skipped: number;
  bytesBefore: number;
  bytesAfter: number;
};

function drawingAbsPath(rel: string): string {
  return path.join(process.cwd(), rel);
}

/**
 * Converts every PNG drawing belonging to students of `groupId` to WebP,
 * updates WorkbookDrawing.filePath, and deletes the PNG only once the DB
 * update has committed. Idempotent — rows already pointing at a .webp file
 * are skipped, so re-running (e.g. from `pnpm archive:pending`) is safe.
 *
 * updatedAt is deliberately left untouched (no `updatedAt: new Date()` in
 * the update) so a mentor/student tab polling drawings doesn't see a
 * spurious "changed" and flash/reload the image.
 */
export async function convertGroupDrawingsToWebp(groupId: number): Promise<WebpConversionResult> {
  const rows = await prisma.workbookDrawing.findMany({
    where: { student: { groupId } },
    select: { studentId: true, fieldId: true, filePath: true }
  });

  const result: WebpConversionResult = { converted: 0, skipped: 0, bytesBefore: 0, bytesAfter: 0 };

  for (const row of rows) {
    if (row.filePath.toLowerCase().endsWith(".webp")) {
      result.skipped++;
      continue;
    }

    const srcAbs = drawingAbsPath(row.filePath);
    let pngBuf: Buffer;
    try {
      pngBuf = await readFile(srcAbs);
    } catch {
      // File already missing — nothing to convert, leave the DB row as is.
      result.skipped++;
      continue;
    }

    const webpBuf = await sharp(pngBuf).webp({ quality: WEBP_QUALITY, alphaQuality: WEBP_ALPHA_QUALITY }).toBuffer();

    const relWebp = path.join("storage", "drawings", String(row.studentId), `${row.fieldId}.webp`);
    const absWebp = drawingAbsPath(relWebp);
    await mkdir(path.dirname(absWebp), { recursive: true });
    await writeFile(absWebp, webpBuf);

    await prisma.workbookDrawing.update({
      where: { studentId_fieldId: { studentId: row.studentId, fieldId: row.fieldId } },
      data: { filePath: relWebp }
    });

    // Only remove the PNG once the DB row points at the new file.
    await rm(srcAbs, { force: true });

    result.converted++;
    result.bytesBefore += pngBuf.byteLength;
    result.bytesAfter += webpBuf.byteLength;
  }

  return result;
}

/** Content-Type for a stored drawing, by file extension. */
export function drawingContentType(filePath: string): string {
  return filePath.toLowerCase().endsWith(".webp") ? "image/webp" : "image/png";
}

// ---------------------------------------------------------------------------
// PDF export (step 4): storage/archive/<groupId>/<student-id>-<slug>.pdf —
// shared naming so the export script, the admin download route and
// `pnpm archive:pending` all agree on where a student's PDF lives.
// ---------------------------------------------------------------------------

export function groupArchiveDir(groupId: number): string {
  return path.join("storage", "archive", String(groupId));
}

/** "<studentId>-<slug-of-full-name>.pdf" — Unicode-aware slug (Cyrillic names stay readable). */
export function studentPdfFileName(studentId: number, fullName: string): string {
  const slug =
    fullName
      .trim()
      .toLowerCase()
      .replace(/[^\p{L}\p{N}]+/gu, "-")
      .replace(/^-+|-+$/g, "") || "student";
  return `${studentId}-${slug}.pdf`;
}

export function studentPdfRelPath(groupId: number, studentId: number, fullName: string): string {
  return path.join(groupArchiveDir(groupId), studentPdfFileName(studentId, fullName));
}
