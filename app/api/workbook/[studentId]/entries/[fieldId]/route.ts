import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canWriteStudent, forbidden, unauthorized } from "@/lib/auth/authorize";
import { getField } from "@/lib/workbook/manifest";
import { notifyWorkbook } from "@/lib/realtime";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_TEXT_LENGTH = 5000;

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ studentId: string; fieldId: string }> }
) {
  const session = await getSession();
  if (!session) return unauthorized();

  const { studentId: studentIdRaw, fieldId } = await params;
  const studentId = Number(studentIdRaw);
  if (!Number.isInteger(studentId)) {
    return NextResponse.json({ ok: false, message: "Некорректный studentId" }, { status: 400 });
  }

  if (!canWriteStudent(session, studentId)) return forbidden();

  const field = getField(fieldId);
  if (!field) {
    return NextResponse.json({ ok: false, message: "Неизвестное поле" }, { status: 400 });
  }
  if (field.type === "canvas") {
    return NextResponse.json(
      { ok: false, message: "Это поле для рисования — используйте /drawings" },
      { status: 400 }
    );
  }

  const body = await request.json().catch(() => null);
  if (!body || !("value" in body)) {
    return NextResponse.json({ ok: false, message: "Отсутствует value" }, { status: 400 });
  }
  const { value } = body as { value: unknown };

  if (field.type === "checkbox") {
    if (typeof value !== "boolean") {
      return NextResponse.json({ ok: false, message: "Ожидалось boolean" }, { status: 400 });
    }
  } else if (field.type === "text" || field.type === "textarea") {
    if (typeof value !== "string") {
      return NextResponse.json({ ok: false, message: "Ожидалась строка" }, { status: 400 });
    }
    if (value.length > MAX_TEXT_LENGTH) {
      return NextResponse.json({ ok: false, message: `Слишком длинный текст (макс. ${MAX_TEXT_LENGTH})` }, {
        status: 400
      });
    }
  }

  const student = await prisma.student.findUnique({ where: { id: studentId }, select: { groupId: true } });
  if (!student) {
    return NextResponse.json({ ok: false, message: "Студент не найден" }, { status: 404 });
  }

  const row = await prisma.workbookEntry.upsert({
    where: { studentId_fieldId: { studentId, fieldId } },
    create: { studentId, fieldId, value: value as never, updatedByTg: BigInt(session.tgUserId) },
    update: { value: value as never, updatedByTg: BigInt(session.tgUserId), updatedAt: new Date() }
  });

  await notifyWorkbook({
    kind: "entry",
    studentId,
    groupId: student.groupId,
    fieldId,
    value,
    updatedAt: row.updatedAt.toISOString()
  });

  return NextResponse.json({ ok: true, updatedAt: row.updatedAt.toISOString() });
}
