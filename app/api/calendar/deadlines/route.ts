import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/prisma";
import { forbidden } from "@/lib/auth/authorize";
import { currentStudent } from "@/lib/live-student";
import { zonedTime } from "@/lib/course";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_DEADLINES = 100;

const input = z.object({
  title: z.string().trim().min(1, "Напишите, что за дедлайн").max(120),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Укажите дату"),
  time: z
    .string()
    .regex(/^\d{2}:\d{2}$/)
    .nullable()
    .optional()
});

/** A personal deadline (olympiad, summer program…), date and optional time in the course time zone. */
export async function POST(request: Request) {
  const student = await currentStudent();
  if (!student) return forbidden();

  const parsed = input.safeParse(await request.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ ok: false, message: parsed.error.issues[0].message }, { status: 400 });
  }
  const { title, date, time } = parsed.data;
  const [y, m, d] = date.split("-").map(Number);
  const [hh, mm] = time ? time.split(":").map(Number) : [0, 0];
  if (m < 1 || m > 12 || d < 1 || d > 31 || hh > 23 || mm > 59 || y < 2020 || y > 2100) {
    return NextResponse.json({ ok: false, message: "Некорректная дата" }, { status: 400 });
  }

  if ((await prisma.studentDeadline.count({ where: { studentId: student.id } })) >= MAX_DEADLINES) {
    return NextResponse.json({ ok: false, message: "Слишком много дедлайнов — удалите прошедшие" }, { status: 400 });
  }
  const created = await prisma.studentDeadline.create({
    data: { studentId: student.id, title, dueAt: zonedTime(y, m - 1, d, hh, mm), allDay: !time }
  });
  return NextResponse.json({ ok: true, id: created.id });
}
