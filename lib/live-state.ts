import { prisma } from "@/lib/prisma";
import {
  acceptsAnswers,
  closesAt,
  isCorrect,
  publicQuestion,
  sessionQuestions,
  summarize,
  type LivePhase
} from "@/lib/live";

/** The group's running session (not finished), if any — at most one per group. */
export function activeSession(groupId: number) {
  return prisma.liveSession.findFirst({
    where: { groupId, finishedAt: null },
    orderBy: { startedAt: "desc" }
  });
}

/**
 * State for the presenter screen (projector + mentor controls). The summary
 * is only computed once the question is revealed, so a projector never
 * spoils answers while the question is still open.
 */
export async function presenterState(sessionId: number) {
  const session = await prisma.liveSession.findUnique({
    where: { id: sessionId },
    include: { group: { select: { name: true } } }
  });
  if (!session) return null;

  const questions = sessionQuestions(session.questions);
  const question = questions[session.currentIndex] ?? null;
  const studentsTotal = await prisma.student.count({ where: { groupId: session.groupId, active: true } });
  const answers = question
    ? await prisma.liveAnswer.findMany({
        where: { sessionId, questionIndex: session.currentIndex },
        select: { value: true }
      })
    : [];
  const phase = session.phase as LivePhase;

  return {
    id: session.id,
    title: session.title,
    groupId: session.groupId,
    groupName: session.group.name,
    phase,
    index: session.currentIndex,
    total: questions.length,
    question,
    closesAt: question ? (closesAt(question, session.openedAt)?.toISOString() ?? null) : null,
    studentsTotal,
    answeredCount: answers.length,
    summary: question && phase === "reveal" ? summarize(question, answers.map((a) => a.value)) : null,
    serverNow: new Date().toISOString()
  };
}

export type PresenterState = NonNullable<Awaited<ReturnType<typeof presenterState>>>;

/**
 * What one student sees: the open question without its right answer, their
 * own answer, and — only at reveal — whether that answer was right.
 */
export async function studentState(studentId: number, groupId: number) {
  const session = await activeSession(groupId);
  if (!session) return { active: false as const };

  const questions = sessionQuestions(session.questions);
  const question = questions[session.currentIndex] ?? null;
  const mine = question
    ? await prisma.liveAnswer.findUnique({
        where: {
          sessionId_questionIndex_studentId: { sessionId: session.id, questionIndex: session.currentIndex, studentId }
        }
      })
    : null;
  const phase = session.phase as LivePhase;

  return {
    active: true as const,
    sessionId: session.id,
    title: session.title,
    phase,
    index: session.currentIndex,
    total: questions.length,
    question: question ? publicQuestion(question) : null,
    closesAt: question ? (closesAt(question, session.openedAt)?.toISOString() ?? null) : null,
    canAnswer: !!question && acceptsAnswers(question, phase, session.openedAt),
    myAnswer: mine ? mine.value : null,
    myCorrect: phase === "reveal" && question && mine ? isCorrect(question, mine.value) : null,
    serverNow: new Date().toISOString()
  };
}

export type StudentLiveState = Awaited<ReturnType<typeof studentState>>;
