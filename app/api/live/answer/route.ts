import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { forbidden } from "@/lib/auth/authorize";
import { currentStudent } from "@/lib/live-student";
import { notifyLive } from "@/lib/realtime";
import { acceptsAnswers, isCorrect, parseAnswer, sessionQuestions } from "@/lib/live";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * { sessionId, questionIndex, value } — while the question is open (and the
 * timer hasn't run out) a student may change their answer; the last one counts.
 */
export async function POST(request: Request) {
  const student = await currentStudent();
  if (!student) return forbidden();

  const body = await request.json().catch(() => null);
  const sessionId = Number(body?.sessionId);
  const questionIndex = Number(body?.questionIndex);
  const live = Number.isInteger(sessionId) ? await prisma.liveSession.findUnique({ where: { id: sessionId } }) : null;
  if (!live || live.groupId !== student.groupId) {
    return NextResponse.json({ ok: false, message: "Сессия не найдена" }, { status: 404 });
  }

  const question = sessionQuestions(live.questions)[live.currentIndex];
  if (!question || questionIndex !== live.currentIndex || !acceptsAnswers(question, live.phase, live.openedAt)) {
    return NextResponse.json({ ok: false, message: "Вопрос уже закрыт" }, { status: 409 });
  }
  const value = parseAnswer(question, body?.value);
  if (value === null) return NextResponse.json({ ok: false, message: "Некорректный ответ" }, { status: 400 });

  const correct = isCorrect(question, value);
  const key = { sessionId, questionIndex, studentId: student.id };
  await prisma.liveAnswer.upsert({
    where: { sessionId_questionIndex_studentId: key },
    create: { ...key, value, correct },
    update: { value, correct, answeredAt: new Date() }
  });
  await notifyLive({ kind: "answer", sessionId, groupId: live.groupId });
  return NextResponse.json({ ok: true });
}
