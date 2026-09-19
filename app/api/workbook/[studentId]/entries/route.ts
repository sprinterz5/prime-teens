import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { authorizeStudentRead, forbidden, unauthorized } from "@/lib/auth/authorize";
import { manifest } from "@/lib/workbook/manifest";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ studentId: string }> }) {
  const studentId = Number((await params).studentId);
  if (!Number.isInteger(studentId)) {
    return NextResponse.json({ ok: false, message: "Некорректный studentId" }, { status: 400 });
  }

  const auth = await authorizeStudentRead(request, studentId);
  if (!auth.ok) return auth.status === 401 ? unauthorized() : forbidden();

  const [rows, drawingRows] = await Promise.all([
    prisma.workbookEntry.findMany({ where: { studentId } }),
    prisma.workbookDrawing.findMany({ where: { studentId }, select: { fieldId: true, updatedAt: true } })
  ]);

  const entries: Record<string, unknown> = {};
  const updatedAt: Record<string, string> = {};
  for (const row of rows) {
    entries[row.fieldId] = row.value;
    updatedAt[row.fieldId] = row.updatedAt.toISOString();
  }

  // Drawing fieldId -> last change, so a polling client can tell which canvases to reload.
  const drawings: Record<string, string> = {};
  for (const row of drawingRows) {
    drawings[row.fieldId] = row.updatedAt.toISOString();
  }

  return NextResponse.json({ version: manifest.version, entries, updatedAt, drawings });
}
