import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { forbidden } from "@/lib/auth/authorize";
import { currentStudent } from "@/lib/live-student";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function DELETE(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const student = await currentStudent();
  if (!student) return forbidden();
  const id = Number((await params).id);
  const deleted = Number.isInteger(id)
    ? await prisma.studentDeadline.deleteMany({ where: { id, studentId: student.id } })
    : { count: 0 };
  if (deleted.count === 0) return NextResponse.json({ ok: false, message: "Не найдено" }, { status: 404 });
  return NextResponse.json({ ok: true });
}
