"use client";

import { useEffect, useState } from "react";
import { LIVE_KINDS, liveKindLabel, type LiveKind, type LiveQuestionData } from "@/lib/live";

type Day = { index: number; title: string };

const TIMERS = [null, 10, 20, 30, 45, 60, 90, 120];

function blankQuestion(kind: LiveKind): LiveQuestionData {
  return {
    kind,
    prompt: "",
    options: kind === "choice" ? ["", ""] : [],
    correctIndex: null,
    timeLimitSec: kind === "text" ? 60 : 30
  };
}

const field =
  "w-full rounded-lg border border-white/15 bg-navy-950 px-3 py-2 text-sm text-white placeholder:text-white/30 focus:border-gold-400 focus:outline-none";

export function ActivityEditor({ id, days }: { id: number | null; days: Day[] }) {
  const [title, setTitle] = useState("");
  const [dayIndex, setDayIndex] = useState<number | null>(null);
  const [questions, setQuestions] = useState<LiveQuestionData[]>([blankQuestion("choice")]);
  const [loading, setLoading] = useState(id !== null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id === null) return;
    fetch(`/api/live/activities/${id}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data) => {
        setTitle(data.title);
        setDayIndex(data.dayIndex);
        setQuestions(data.questions);
      })
      .catch(() => setError("Не удалось загрузить шаблон"))
      .finally(() => setLoading(false));
  }, [id]);

  function update(index: number, patch: Partial<LiveQuestionData>) {
    setQuestions((qs) => qs.map((q, i) => (i === index ? { ...q, ...patch } : q)));
  }

  function move(index: number, delta: number) {
    setQuestions((qs) => {
      const target = index + delta;
      if (target < 0 || target >= qs.length) return qs;
      const next = [...qs];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  function setOption(qi: number, oi: number, value: string) {
    const q = questions[qi];
    update(qi, { options: q.options.map((o, i) => (i === oi ? value : o)) });
  }

  function removeOption(qi: number, oi: number) {
    const q = questions[qi];
    let correctIndex = q.correctIndex;
    if (correctIndex === oi) correctIndex = null;
    else if (correctIndex !== null && correctIndex > oi) correctIndex -= 1;
    update(qi, { options: q.options.filter((_, i) => i !== oi), correctIndex });
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(id === null ? "/api/live/activities" : `/api/live/activities/${id}`, {
        method: id === null ? "POST" : "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, dayIndex, questions })
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.ok) {
        setError(data?.message ?? `Ошибка ${res.status}`);
        return;
      }
      window.location.href = "/studio";
    } catch {
      setError("Нет связи с сервером");
    } finally {
      setSaving(false);
    }
  }

  async function archive() {
    if (id === null || !window.confirm("Убрать шаблон? Проведённые сессии и их итоги останутся.")) return;
    const res = await fetch(`/api/live/activities/${id}`, { method: "DELETE" });
    if (res.ok) window.location.href = "/studio";
    else setError(`Ошибка ${res.status}`);
  }

  if (loading) return <p className="px-4 py-8 text-sm text-muted">Загружаем…</p>;

  return (
    <main className="mx-auto max-w-3xl px-4 pb-24 pt-6">
      <div className="grid gap-3 sm:grid-cols-[1fr_220px]">
        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted">Название</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} placeholder="Дебаты: выбери сторону" className={`${field} mt-1`} />
        </label>
        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted">К какому дню</span>
          <select
            value={dayIndex ?? ""}
            onChange={(e) => setDayIndex(e.target.value ? Number(e.target.value) : null)}
            className={`${field} mt-1`}
          >
            <option value="">Любой день</option>
            {days.map((d) => (
              <option key={d.index} value={d.index}>
                День {d.index} · {d.title}
              </option>
            ))}
          </select>
        </label>
      </div>

      <ol className="mt-6 space-y-4">
        {questions.map((q, qi) => (
          <li key={qi} className="rounded-xl border border-white/10 bg-navy-900 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-display text-sm font-semibold text-gold-400">Вопрос {qi + 1}</span>
              <select
                value={q.kind}
                onChange={(e) => {
                  const kind = e.target.value as LiveKind;
                  update(qi, { ...blankQuestion(kind), prompt: q.prompt, timeLimitSec: q.timeLimitSec });
                }}
                className="rounded-lg border border-white/15 bg-navy-950 px-2 py-1 text-xs text-white"
              >
                {LIVE_KINDS.map((k) => (
                  <option key={k} value={k}>
                    {liveKindLabel[k]}
                  </option>
                ))}
              </select>
              <select
                value={q.timeLimitSec ?? ""}
                onChange={(e) => update(qi, { timeLimitSec: e.target.value ? Number(e.target.value) : null })}
                className="rounded-lg border border-white/15 bg-navy-950 px-2 py-1 text-xs text-white"
                aria-label="Таймер"
              >
                {TIMERS.map((t) => (
                  <option key={t ?? "none"} value={t ?? ""}>
                    {t ? `${t} сек` : "Без таймера"}
                  </option>
                ))}
              </select>
              <span className="ml-auto flex gap-1 text-xs">
                <button type="button" onClick={() => move(qi, -1)} disabled={qi === 0} className="rounded px-2 py-1 text-muted hover:text-champagne disabled:opacity-30">
                  ↑
                </button>
                <button
                  type="button"
                  onClick={() => move(qi, 1)}
                  disabled={qi === questions.length - 1}
                  className="rounded px-2 py-1 text-muted hover:text-champagne disabled:opacity-30"
                >
                  ↓
                </button>
                <button
                  type="button"
                  onClick={() => setQuestions((qs) => qs.filter((_, i) => i !== qi))}
                  disabled={questions.length === 1}
                  className="rounded px-2 py-1 text-red-300 hover:text-red-200 disabled:opacity-30"
                >
                  Удалить
                </button>
              </span>
            </div>

            <textarea
              value={q.prompt}
              onChange={(e) => update(qi, { prompt: e.target.value })}
              rows={2}
              maxLength={300}
              placeholder={
                q.kind === "scale" ? "Насколько убедительным был питч?" : q.kind === "text" ? "Одно слово: что для тебя успех?" : "Вопрос"
              }
              className={`${field} mt-3`}
            />

            {q.kind === "choice" && (
              <div className="mt-3 space-y-2">
                {q.options.map((o, oi) => (
                  <div key={oi} className="flex items-center gap-2">
                    <input
                      type="radio"
                      name={`correct-${qi}`}
                      checked={q.correctIndex === oi}
                      onChange={() => update(qi, { correctIndex: oi })}
                      title="Правильный ответ"
                      className="h-4 w-4 accent-[#C9A24B]"
                    />
                    <input value={o} onChange={(e) => setOption(qi, oi, e.target.value)} maxLength={80} placeholder={`Вариант ${oi + 1}`} className={field} />
                    <button
                      type="button"
                      onClick={() => removeOption(qi, oi)}
                      disabled={q.options.length <= 2}
                      className="px-2 text-muted hover:text-red-300 disabled:opacity-30"
                      aria-label="Убрать вариант"
                    >
                      ×
                    </button>
                  </div>
                ))}
                <div className="flex flex-wrap items-center gap-3 text-xs">
                  {q.options.length < 6 && (
                    <button type="button" onClick={() => update(qi, { options: [...q.options, ""] })} className="text-champagne hover:text-gold-400">
                      + вариант
                    </button>
                  )}
                  <label className="flex items-center gap-1.5 text-muted">
                    <input
                      type="radio"
                      name={`correct-${qi}`}
                      checked={q.correctIndex === null}
                      onChange={() => update(qi, { correctIndex: null })}
                      className="h-3.5 w-3.5 accent-[#C9A24B]"
                    />
                    Без правильного ответа (опрос, «выбери сторону»)
                  </label>
                </div>
              </div>
            )}
            {q.kind === "scale" && <p className="mt-2 text-xs text-muted">Ученики ставят от 1 до 5, на экране — распределение и среднее.</p>}
            {q.kind === "text" && <p className="mt-2 text-xs text-muted">Короткий ответ до 60 символов, на экране — облако слов после «Показать итоги».</p>}
          </li>
        ))}
      </ol>

      <div className="mt-4 flex flex-wrap gap-2 text-xs">
        {LIVE_KINDS.map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setQuestions((qs) => [...qs, blankQuestion(k)])}
            disabled={questions.length >= 30}
            className="rounded-lg border border-white/15 px-3 py-2 text-muted hover:border-gold-400 hover:text-champagne"
          >
            + {liveKindLabel[k]}
          </button>
        ))}
      </div>

      <div className="sticky bottom-0 mt-8 flex flex-wrap items-center gap-3 border-t border-white/10 bg-navy-950 py-4">
        <button type="button" onClick={save} disabled={saving} className="btn btn-primary focus-ring h-11 disabled:opacity-50">
          {saving ? "Сохраняем…" : "Сохранить"}
        </button>
        {id !== null && (
          <button type="button" onClick={archive} className="text-sm text-muted underline hover:text-red-300">
            Убрать шаблон
          </button>
        )}
        {error && <p className="text-sm text-red-400">{error}</p>}
      </div>
    </main>
  );
}
