"use client";

import { useCallback, useEffect, useState } from "react";
import { homeworkStatusLabel, isHomeworkStatus } from "@/lib/homework";

type Day = { index: number; title: string; homework: string };
type Student = { id: number; fullName: string; shortName: string | null };
type Submission = {
  studentId: number;
  dayIndex: number;
  text: string;
  status: string;
  mentorComment: string | null;
  submittedAt: string;
  reviewedAt: string | null;
  reviewerName: string | null;
};
type Data = { days: Day[]; students: Student[]; submissions: Submission[] };

const statusClass = {
  submitted: "bg-white/10 text-champagne",
  accepted: "bg-emerald-500/15 text-emerald-300",
  returned: "bg-orange-500/15 text-orange-300"
} as const;

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function HomeworkReview({ groupId }: { groupId: number }) {
  const [data, setData] = useState<Data | null>(null);
  const [day, setDay] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    return fetch(`/api/mentor/groups/${groupId}/homework`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d: Data) => {
        setData(d);
        setDay((current) => {
          if (current !== null) return current;
          // Start on the day with the most submissions still waiting for review.
          const waiting = (index: number) =>
            d.submissions.filter((s) => s.dayIndex === index && s.status === "submitted").length;
          const busiest = [...d.days].sort((a, b) => waiting(b.index) - waiting(a.index))[0];
          return busiest && waiting(busiest.index) > 0 ? busiest.index : (d.days[0]?.index ?? null);
        });
      })
      .catch(() => setError("Не удалось загрузить домашку"));
  }, [groupId]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) return <p className="px-4 py-8 text-sm text-red-400">{error}</p>;
  if (!data) return <p className="px-4 py-8 text-sm text-muted">Загружаем…</p>;
  if (data.days.length === 0) return <p className="px-4 py-8 text-sm text-muted">В программе курса нет домашки.</p>;

  const current = data.days.find((d) => d.index === day) ?? data.days[0];
  const byStudent = new Map(
    data.submissions.filter((s) => s.dayIndex === current.index).map((s) => [s.studentId, s])
  );
  const submitted = data.students.filter((s) => byStudent.has(s.id));
  const missing = data.students.filter((s) => !byStudent.has(s.id));

  return (
    <main className="mx-auto max-w-3xl px-4 pb-16 pt-6">
      <div className="flex flex-wrap gap-2">
        {data.days.map((d) => {
          const waiting = data.submissions.filter((s) => s.dayIndex === d.index && s.status === "submitted").length;
          return (
            <button
              key={d.index}
              type="button"
              onClick={() => setDay(d.index)}
              className={`rounded-lg border px-3 py-2 text-xs font-semibold ${
                d.index === current.index ? "border-gold-400 text-gold-400" : "border-white/15 text-muted hover:text-champagne"
              }`}
            >
              День {d.index}
              {waiting > 0 && <span className="ml-1.5 rounded-full bg-gold-500 px-1.5 text-navy-950">{waiting}</span>}
            </button>
          );
        })}
      </div>

      <h1 className="mt-6 font-display text-xl font-semibold">
        День {current.index} · {current.title}
      </h1>
      <p className="mt-1 text-sm text-muted">Задание: {current.homework}</p>
      <p className="mt-1 text-xs text-muted">
        Сдали {submitted.length} из {data.students.length}
      </p>

      <ul className="mt-5 space-y-3">
        {submitted.map((student) => (
          <SubmissionCard
            key={`${student.id}:${current.index}`}
            student={student}
            submission={byStudent.get(student.id)!}
            onReviewed={load}
          />
        ))}
      </ul>

      {missing.length > 0 && (
        <p className="mt-6 text-sm text-muted">
          Не сдали: {missing.map((s) => s.shortName ?? s.fullName).join(", ")}
        </p>
      )}
    </main>
  );
}

function SubmissionCard({
  student,
  submission,
  onReviewed
}: {
  student: Student;
  submission: Submission;
  onReviewed: () => Promise<void>;
}) {
  const [comment, setComment] = useState(submission.mentorComment ?? "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const status = isHomeworkStatus(submission.status) ? submission.status : "submitted";

  async function review(next: "accepted" | "returned") {
    setPending(true);
    setError(null);
    try {
      const res = await fetch("/api/mentor/homework", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          studentId: submission.studentId,
          day: submission.dayIndex,
          status: next,
          comment,
          submittedAt: submission.submittedAt
        })
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.ok) {
        setError(data?.message ?? `Ошибка ${res.status}`);
        if (res.status === 409) await onReviewed();
      } else {
        await onReviewed();
      }
    } catch {
      setError("Нет связи с сервером");
    } finally {
      setPending(false);
    }
  }

  return (
    <li className="rounded-xl border border-white/10 bg-navy-900 px-4 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-semibold text-porcelain">{student.fullName}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs ${statusClass[status]}`}>{homeworkStatusLabel[status]}</span>
      </div>
      <p className="mt-2 whitespace-pre-wrap break-words text-sm">{submission.text}</p>
      <p className="mt-2 text-xs text-muted">
        Сдано {formatTime(submission.submittedAt)}
        {submission.reviewedAt &&
          ` · проверено ${formatTime(submission.reviewedAt)}${submission.reviewerName ? `, ${submission.reviewerName}` : ""}`}
      </p>
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        rows={2}
        maxLength={2000}
        placeholder="Комментарий ученику (обязателен, если возвращаете)"
        className="mt-3 w-full rounded-lg border border-white/15 bg-navy-950 px-3 py-2 text-sm text-white placeholder:text-white/30 focus:border-gold-400 focus:outline-none"
      />
      {error && <p className="mt-1 text-sm text-red-400">{error}</p>}
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          disabled={pending}
          onClick={() => review("accepted")}
          className="rounded-lg bg-gold-500 px-3 py-2 text-xs font-semibold text-navy-950 disabled:opacity-50"
        >
          Принять
        </button>
        <button
          type="button"
          disabled={pending}
          onClick={() => review("returned")}
          className="rounded-lg border border-white/15 px-3 py-2 text-xs font-semibold text-muted hover:text-champagne disabled:opacity-50"
        >
          Вернуть на доработку
        </button>
      </div>
    </li>
  );
}
