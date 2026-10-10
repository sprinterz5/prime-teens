"use client";

import { useState } from "react";
import { HOMEWORK_MAX_LENGTH, homeworkStatusLabel, isHomeworkStatus } from "@/lib/homework";

type Submission = { text: string; status: string; mentorComment: string | null; submittedAt: string };

const statusClass = {
  submitted: "text-champagne",
  accepted: "text-emerald-300",
  returned: "text-orange-300"
} as const;

export function HomeworkPanel({
  day,
  task,
  due,
  readonly,
  initial
}: {
  day: number;
  task: string;
  due: string | null;
  readonly: boolean;
  initial: Submission | null;
}) {
  const [submission, setSubmission] = useState<Submission | null>(initial);
  const [draft, setDraft] = useState(initial?.text ?? "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Open only on first render: re-rendering after a submit must not fold the panel under the student.
  const [initiallyOpen] = useState(!initial && !readonly);

  const status = submission && isHomeworkStatus(submission.status) ? submission.status : null;
  const locked = readonly || status === "accepted";
  const dirty = draft.trim() !== (submission?.text ?? "");

  async function submit() {
    setPending(true);
    setError(null);
    try {
      const res = await fetch(`/api/homework/${day}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: draft })
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.ok) setError(data?.message ?? `Ошибка ${res.status}`);
      else setSubmission(data.homework);
    } catch {
      setError("Нет связи с сервером");
    } finally {
      setPending(false);
    }
  }

  return (
    <details open={initiallyOpen}className="shrink-0 border-b border-white/10 bg-navy-900 text-sm">
      <summary className="flex cursor-pointer items-center gap-2 px-3 py-2">
        <span className="font-semibold text-porcelain">Домашка</span>
        <span className={status ? statusClass[status] : "text-muted"}>
          · {status ? homeworkStatusLabel[status] : "не сдана"}
        </span>
        {due && !status && <span className="ml-auto text-xs text-muted">до {due}</span>}
      </summary>
      <div className="max-h-[50dvh] overflow-y-auto px-3 pb-3">
        <p className="text-porcelain">{task}</p>
        {submission?.mentorComment && (
          <p className="mt-2 rounded-lg bg-white/5 px-3 py-2 text-muted">
            <span className="text-champagne">Наставник:</span> {submission.mentorComment}
          </p>
        )}
        {locked ? (
          submission && <p className="mt-2 whitespace-pre-wrap text-muted">{submission.text}</p>
        ) : (
          <>
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={HOMEWORK_MAX_LENGTH}
              rows={4}
              placeholder="Ответ, ссылка на презентацию или файл в Google Drive…"
              className="mt-2 w-full rounded-lg border border-white/15 bg-navy-950 px-3 py-2 text-base text-white placeholder:text-white/30 focus:border-gold-400 focus:outline-none sm:text-sm"
            />
            {error && <p className="mt-1 text-red-400">{error}</p>}
            <button
              type="button"
              onClick={submit}
              disabled={pending || !draft.trim() || !dirty}
              className="btn btn-primary focus-ring mt-2 h-10 disabled:opacity-50"
            >
              {pending ? "Отправляем…" : submission ? "Отправить исправленную" : "Сдать"}
            </button>
          </>
        )}
      </div>
    </details>
  );
}
