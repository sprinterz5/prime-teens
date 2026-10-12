import { z } from "zod";

/**
 * Live mode: a mentor runs a short interactive in class (quiz, poll, 1–5
 * scale, word cloud), students answer from their phones, the projector shows
 * the result. Course directors edit templates in /studio; starting a session
 * copies the questions into live_sessions.questions, so later edits never
 * touch answers already collected.
 *
 * No-stress rule: the projector only ever shows aggregates (counts, average,
 * words) — never names or a ranking. A student sees whether *their own* quiz
 * answer was right at reveal time; afterwards only "выполнено". Per-student
 * answers are for the group's mentor (/mentor/live/[sessionId]).
 */

export const LIVE_KINDS = ["choice", "scale", "text"] as const;
export type LiveKind = (typeof LIVE_KINDS)[number];
export type LivePhase = "lobby" | "open" | "reveal" | "finished";

export const liveKindLabel: Record<LiveKind, string> = {
  choice: "Варианты (квиз или опрос)",
  scale: "Шкала 1–5",
  text: "Короткий ответ (облако слов)"
};

export const SCALE_MAX = 5;
export const TEXT_ANSWER_MAX = 60;
/** Answers arriving this long after the timer are still accepted (network lag). */
const ANSWER_GRACE_MS = 2000;

export type LiveQuestionData = {
  kind: LiveKind;
  prompt: string;
  options: string[];
  correctIndex: number | null;
  timeLimitSec: number | null;
};

const questionSchema = z
  .object({
    kind: z.enum(LIVE_KINDS),
    prompt: z.string().trim().min(1, "Пустой вопрос").max(300),
    options: z.array(z.string().trim().min(1, "Пустой вариант").max(80)).max(6),
    correctIndex: z.number().int().min(0).nullable(),
    timeLimitSec: z.number().int().min(5).max(600).nullable()
  })
  .superRefine((q, ctx) => {
    if (q.kind === "choice") {
      if (q.options.length < 2) ctx.addIssue({ code: "custom", message: "Нужно хотя бы 2 варианта" });
      if (q.correctIndex !== null && q.correctIndex >= q.options.length) {
        ctx.addIssue({ code: "custom", message: "Правильный ответ вне списка вариантов" });
      }
    }
  })
  // Scale and text questions carry no options or right answer.
  .transform((q): LiveQuestionData =>
    q.kind === "choice" ? q : { ...q, options: [], correctIndex: null }
  );

export const activityInputSchema = z.object({
  title: z.string().trim().min(1, "Нужно название").max(120),
  dayIndex: z.number().int().min(1).nullable(),
  questions: z.array(questionSchema).min(1, "Добавьте хотя бы один вопрос").max(30)
});

export type ActivityInput = z.infer<typeof activityInputSchema>;

/** First zod issue as a human message, for 400 responses. */
export function firstIssue(error: z.ZodError): string {
  const issue = error.issues[0];
  const where = issue.path[0] === "questions" && typeof issue.path[1] === "number" ? `Вопрос ${issue.path[1] + 1}: ` : "";
  return where + issue.message;
}

/** Normalizes a raw answer for a question, or null if it doesn't fit. */
export function parseAnswer(q: LiveQuestionData, raw: unknown): number | string | null {
  if (q.kind === "choice") {
    return typeof raw === "number" && Number.isInteger(raw) && raw >= 0 && raw < q.options.length ? raw : null;
  }
  if (q.kind === "scale") {
    return typeof raw === "number" && Number.isInteger(raw) && raw >= 1 && raw <= SCALE_MAX ? raw : null;
  }
  if (typeof raw !== "string") return null;
  const text = raw.trim().replace(/\s+/g, " ");
  return text && text.length <= TEXT_ANSWER_MAX ? text : null;
}

/** true/false for a quiz question, null when there is no right answer. */
export function isCorrect(q: LiveQuestionData, value: unknown): boolean | null {
  if (q.kind !== "choice" || q.correctIndex === null) return null;
  return value === q.correctIndex;
}

/** When the open question stops taking answers; null — no timer. */
export function closesAt(q: LiveQuestionData, openedAt: Date | null): Date | null {
  if (!q.timeLimitSec || !openedAt) return null;
  return new Date(openedAt.getTime() + q.timeLimitSec * 1000);
}

export function acceptsAnswers(q: LiveQuestionData, phase: string, openedAt: Date | null, now = new Date()): boolean {
  if (phase !== "open") return false;
  const deadline = closesAt(q, openedAt);
  return !deadline || now.getTime() <= deadline.getTime() + ANSWER_GRACE_MS;
}

export type LiveSummary =
  | { kind: "choice"; counts: number[]; correctIndex: number | null }
  | { kind: "scale"; counts: number[]; average: number | null }
  | { kind: "text"; words: { text: string; count: number }[] };

/** What the projector shows at reveal: aggregates only, never who answered what. */
export function summarize(q: LiveQuestionData, values: unknown[]): LiveSummary {
  if (q.kind === "choice") {
    const counts = q.options.map(() => 0);
    for (const v of values) if (typeof v === "number" && counts[v] !== undefined) counts[v] += 1;
    return { kind: "choice", counts, correctIndex: q.correctIndex };
  }
  if (q.kind === "scale") {
    const counts = Array.from({ length: SCALE_MAX }, () => 0);
    const nums = values.filter((v): v is number => typeof v === "number" && v >= 1 && v <= SCALE_MAX);
    for (const v of nums) counts[v - 1] += 1;
    const average = nums.length ? Math.round((nums.reduce((a, b) => a + b, 0) / nums.length) * 10) / 10 : null;
    return { kind: "scale", counts, average };
  }
  const byKey = new Map<string, { text: string; count: number }>();
  for (const v of values) {
    if (typeof v !== "string") continue;
    const key = v.toLocaleLowerCase("ru-RU");
    const entry = byKey.get(key);
    if (entry) entry.count += 1;
    else byKey.set(key, { text: v, count: 1 });
  }
  const words = [...byKey.values()].sort((a, b) => b.count - a.count).slice(0, 40);
  return { kind: "text", words };
}

/** The questions snapshot stored on a session (jsonb) back as typed data. */
export function sessionQuestions(raw: unknown): LiveQuestionData[] {
  return Array.isArray(raw) ? (raw as LiveQuestionData[]) : [];
}

/** A question as students see it while it is open: no right answer. */
export function publicQuestion(q: LiveQuestionData) {
  return { kind: q.kind, prompt: q.prompt, options: q.options, timeLimitSec: q.timeLimitSec };
}
