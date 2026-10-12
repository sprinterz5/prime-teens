"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { PresenterState } from "@/lib/live-state";
import { SummaryView, LETTERS, OPTION_COLORS } from "@/components/live/summary-view";
import { secondsLeft, useLiveFeed } from "@/components/live/use-live-feed";

/**
 * Projector screen with the mentor's controls at the bottom. Big type, only
 * aggregates. When the timer runs out or everyone has answered it reveals
 * by itself (the server ignores a duplicate reveal, see control route).
 */
export function Presenter({ id, joinHint }: { id: number; joinHint: string }) {
  const [state, setState] = useState<PresenterState | null>(null);
  const [offset, setOffset] = useState(0);
  const [, setTick] = useState(0);
  const [busy, setBusy] = useState(false);
  const autoRevealed = useRef<number | null>(null);

  const load = useCallback(() => {
    fetch(`/api/live/sessions/${id}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((s: PresenterState | null) => {
        if (!s) return;
        setState(s);
        setOffset(new Date(s.serverNow).getTime() - Date.now());
      })
      .catch(() => {});
  }, [id]);

  useEffect(load, [load]);
  useLiveFeed(`/api/live/sessions/${id}/stream`, load);
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 500);
    return () => clearInterval(t);
  }, []);

  const control = useCallback(
    async (action: "next" | "reveal" | "finish", from: number) => {
      setBusy(true);
      await fetch(`/api/live/sessions/${id}/control`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, from })
      }).catch(() => {});
      setBusy(false);
      load();
    },
    [id, load]
  );

  const left = state ? secondsLeft(state.closesAt, offset) : null;
  const everyoneAnswered = !!state && state.studentsTotal > 0 && state.answeredCount >= state.studentsTotal;

  useEffect(() => {
    if (!state || state.phase !== "open" || autoRevealed.current === state.index) return;
    if (left === 0 || everyoneAnswered) {
      autoRevealed.current = state.index;
      control("reveal", state.index);
    }
  }, [state, left, everyoneAnswered, control]);

  if (!state) return <main className="flex min-h-[100dvh] items-center justify-center bg-navy-950 text-muted">Загружаем…</main>;

  const q = state.question;
  return (
    <main className="flex min-h-[100dvh] flex-col bg-navy-950 text-white">
      <header className="flex items-center justify-between gap-4 px-6 pt-5 text-sm text-muted sm:px-10">
        <span className="truncate">
          {state.title} · {state.groupName}
        </span>
        {state.index >= 0 && state.phase !== "finished" && (
          <span className="shrink-0">
            Вопрос {state.index + 1} из {state.total}
          </span>
        )}
      </header>

      <section className="flex flex-1 flex-col items-center justify-center px-6 py-8 text-center sm:px-10">
        {state.phase === "lobby" && (
          <>
            <p className="font-display text-4xl font-semibold sm:text-6xl">{state.title}</p>
            <p className="mt-6 text-xl text-muted sm:text-2xl">
              Откройте <span className="text-champagne">{joinHint}</span> — там появится «Идёт live»
            </p>
          </>
        )}

        {q && (state.phase === "open" || state.phase === "reveal") && (
          <div className="w-full max-w-5xl">
            <p className="font-display text-3xl font-semibold leading-tight sm:text-5xl">{q.prompt}</p>

            {state.phase === "open" && (
              <>
                {q.kind === "choice" && (
                  <ul className="mx-auto mt-10 grid max-w-4xl gap-4 text-left sm:grid-cols-2">
                    {q.options.map((o, i) => (
                      <li
                        key={i}
                        className="flex items-center gap-4 rounded-2xl px-5 py-4 text-xl font-semibold text-navy-950 sm:text-2xl"
                        style={{ backgroundColor: OPTION_COLORS[i] }}
                      >
                        <span className="font-display">{LETTERS[i]}</span>
                        {o}
                      </li>
                    ))}
                  </ul>
                )}
                {q.kind === "scale" && <p className="mt-8 text-2xl text-muted">Оцените от 1 до 5 на телефоне</p>}
                {q.kind === "text" && <p className="mt-8 text-2xl text-muted">Напишите коротко на телефоне</p>}
                <div className="mt-10 flex items-center justify-center gap-10 text-2xl">
                  {left !== null && <span className={`font-display text-6xl ${left <= 5 ? "text-orange-300" : "text-gold-400"}`}>{left}</span>}
                  <span className="text-muted">
                    Ответили {state.answeredCount} из {state.studentsTotal}
                  </span>
                </div>
              </>
            )}

            {state.phase === "reveal" && state.summary && (
              <div className="mx-auto mt-10 max-w-4xl text-left">
                <SummaryView question={q} summary={state.summary} large />
              </div>
            )}
          </div>
        )}

        {state.phase === "finished" && (
          <>
            <p className="font-display text-5xl font-semibold">Готово!</p>
            <p className="mt-4 text-xl text-muted">Спасибо всем за ответы</p>
          </>
        )}
      </section>

      <footer className="flex flex-wrap items-center justify-center gap-3 border-t border-white/10 px-6 py-3 text-sm">
        {state.phase === "lobby" && (
          <button type="button" disabled={busy} onClick={() => control("next", state.index)} className="btn btn-primary h-11 disabled:opacity-50">
            Начать
          </button>
        )}
        {state.phase === "open" && (
          <button type="button" disabled={busy} onClick={() => control("reveal", state.index)} className="btn btn-primary h-11 disabled:opacity-50">
            Показать итоги
          </button>
        )}
        {state.phase === "reveal" && (
          <button type="button" disabled={busy} onClick={() => control("next", state.index)} className="btn btn-primary h-11 disabled:opacity-50">
            {state.index + 1 < state.total ? "Следующий вопрос" : "Завершить"}
          </button>
        )}
        {state.phase !== "finished" ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => window.confirm("Завершить live для группы?") && control("finish", state.index)}
            className="text-muted underline hover:text-champagne"
          >
            Завершить сейчас
          </button>
        ) : (
          <a href={`/mentor/live/${state.id}`} className="text-champagne underline">
            Итоги по ученикам (видите только вы)
          </a>
        )}
      </footer>
    </main>
  );
}
