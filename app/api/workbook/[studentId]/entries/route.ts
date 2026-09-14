import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canReadStudent, forbidden, unauthorized } from "@/lib/auth/authorize";
import { manifest } from "@/lib/workbook/manifest";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_request: Request, { params }: { params: Promise<{ studentId: string }> }) {
  const session = await getSession();
  if (!session) return unauthorized();

  const studentId = Number((await params).studentId);
  if (!Number.isInteger(studentId)) {
    return NextResponse.json({ ok: false, message: "Некорректный studentId" }, { status: 400 });
  }

  if (!(await canReadStudent(session, studentId))) return forbidden();

  const rows = await prisma.workbookEntry.findMany({ where: { studentId } });

  const entries: Record<string, unknown> = {};
  const updatedAt: Record<string, string> = {};
  for (const row of rows) {
    entries[row.fieldId] = row.value;
    updatedAt[row.fieldId] = row.updatedAt.toISOString();
  }

  return NextResponse.json({ version: manifest.version, entries, updatedAt });
}
