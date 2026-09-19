import { NextResponse } from "next/server";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { authorizeStudentRead, canWriteStudent, forbidden, unauthorized } from "@/lib/auth/authorize";
import { getField } from "@/lib/workbook/manifest";
import { notifyWorkbook } from "@/lib/realtime";
import { archivedResponse, drawingContentType, getStudentGroupInfo } from "@/lib/workbook/archive";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_PNG_BYTES = 2 * 1024 * 1024;
const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

function isPng(buf: Buffer): boolean {
  return buf.length >= 8 && buf.subarray(0, 8).equals(PNG_SIGNATURE);
}

function relPath(studentId: number, fieldId: string): string {
  return path.join("storage", "drawings", String(studentId), `${fieldId}.png`);
}

async function resolveParams(params: Promise<{ studentId: string; fieldId: string }>) {
  const { studentId: studentIdRaw, fieldId } = await params;
  return { studentId: Number(studentIdRaw), fieldId };
}

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ studentId: string; fieldId: string }> }
) {
  const session = await getSession();
  if (!session) return unauthorized();

  const { studentId, fieldId } = await resolveParams(params);
  if (!Number.isInteger(studentId)) {
    return NextResponse.json({ ok: false, message: "Некорректный studentId" }, { status: 400 });
  }
  if (!canWriteStudent(session, studentId)) return forbidden();

  const field = getField(fieldId);
  if (!field || field.type !== "canvas") {
    return NextResponse.json({ ok: false, message: "Неизвестная область рисования" }, { status: 400 });
  }

  const arrayBuffer = await request.arrayBuffer();
  const buf = Buffer.from(arrayBuffer);
  if (buf.byteLength === 0) {
    return NextResponse.json({ ok: false, message: "Пустое тело запроса" }, { status: 400 });
  }
  if (buf.byteLength > MAX_PNG_BYTES) {
    return NextResponse.json({ ok: false, message: "Файл больше 2 МБ" }, { status: 400 });
  }
  if (!isPng(buf)) {
    return NextResponse.json({ ok: false, message: "Ожидался PNG" }, { status: 400 });
  }

  const info = await getStudentGroupInfo(studentId);
  if (!info) {
    return NextResponse.json({ ok: false, message: "Студент не найден" }, { status: 404 });
  }
  if (info.archivedAt) return archivedResponse();

  // A drawing saved after "Вернуть в работу" always writes a fresh PNG at the
  // .png path, even if the archived version was compressed to .webp — find
  // out now so the stale .webp can be removed once the new file is in place.
  const existing = await prisma.workbookDrawing.findUnique({
    where: { studentId_fieldId: { studentId, fieldId } },
    select: { filePath: true }
  });

  const rel = relPath(studentId, fieldId);
  const abs = path.join(process.cwd(), rel);
  await mkdir(path.dirname(abs), { recursive: true });
  await writeFile(abs, buf);

  const row = await prisma.workbookDrawing.upsert({
    where: { studentId_fieldId: { studentId, fieldId } },
    create: { studentId, fieldId, filePath: rel },
    update: { filePath: rel, updatedAt: new Date() }
  });

  if (existing && existing.filePath !== rel && existing.filePath.toLowerCase().endsWith(".webp")) {
    await rm(path.join(process.cwd(), existing.filePath), { force: true });
  }

  await notifyWorkbook({
    kind: "drawing",
    studentId,
    groupId: info.groupId,
    fieldId,
    updatedAt: row.updatedAt.toISOString()
  });

  return NextResponse.json({ ok: true, updatedAt: row.updatedAt.toISOString() });
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ studentId: string; fieldId: string }> }
) {
  const { studentId, fieldId } = await resolveParams(params);
  if (!Number.isInteger(studentId)) {
    return NextResponse.json({ ok: false, message: "Некорректный studentId" }, { status: 400 });
  }
  const auth = await authorizeStudentRead(request, studentId);
  if (!auth.ok) return auth.status === 401 ? unauthorized() : forbidden();

  const row = await prisma.workbookDrawing.findUnique({
    where: { studentId_fieldId: { studentId, fieldId } }
  });
  if (!row) {
    return NextResponse.json({ ok: false, message: "Рисунок не найден" }, { status: 404 });
  }

  try {
    const buf = await readFile(path.join(process.cwd(), row.filePath));
    return new NextResponse(new Uint8Array(buf), {
      status: 200,
      headers: {
        "Content-Type": drawingContentType(row.filePath),
        "Cache-Control": "private, no-store"
      }
    });
  } catch {
    return NextResponse.json({ ok: false, message: "Файл рисунка отсутствует" }, { status: 404 });
  }
}
