"use client";

import { useCallback, useEffect, useState } from "react";
import type { StudentLiveState } from "@/lib/live-state";
import { LETTERS, OPTION_COLORS } from "@/components/live/summary-view";
import { secondsLeft, useLiveFeed } from "@/components/live/use-live-feed";

/**
 * The student's phone during a live session: answer, see "принято", and at
 * reveal only whether *their own* quiz answer was right. Never a score or a
 * place in a ranking.
 */
export function LiveAnswer() {
  const [state, setState] = useState<StudentLiveState | null>(null);
  const [offset, setOffset] = useState(0);
  const [, setTick] = useState(0);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    fetch("/api/live/current", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((s: StudentLiveState | null) => {
        if (!s) return;
        setState(s);
        if (s.active) setOffset(new Date(s.serverNow).getTime() - Date.now());
      })
      .catch(() => {});
  }, []);

  useEffect(load, [load]);
  useLiveFeed("/api/live/stream", load);
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 500);
    return () => clearInterval(t);
  }, []);

  const questionKey = state?.active ? `${state.sessionId}:${state.index}` : "";
  useEffect(() => {
    setText(state?.active && typeof state.myAnswer === "string" ? state.myAnswer : "");
    setError(null);
    // Reset the text box only when the question changes, not on every refetch.
  }, [questionKey]);

  async function answer(value: number | string) {
    if (!state?.active) return;
    setSending(true);
    setError(null);
    try {
      const res = await fetch("/api/live/answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: state.sessionId, questionIndex: state.index, value })
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.ok) setError(data?.message ?? `Ошибка ${res.status}`);
      load();
    } catch {
      setError("Нет связи — попробуй ещё раз");
    } finally {
      setSending(false);
    }
  }

  if (!state) return <Center>Подключаемся…</Center>;
  if (!state.active) {
    return (
      <Center>
        <p className="font-display text-xl font-semibold">Сейчас live нет</p>
        <p className="mt-2 text-sm text-muted">Когда наставник запустит задание, оно появится здесь само.</p>
      </Center>
    );
  }

  const q = state.question;
  const left = secondsLeft(state.closesAt, offset);
  const timeUp = state.phase === "open" && left === 0;
  const answered = state.myAnswer !== null;

  if (state.phase === "lobby" || !q) {
    return (
      <Center>
        <p className="text-sm text-muted">{state.title}</p>
        <p className="mt-2 font-display text-xl font-semibold">Ты в игре — ждём начала</p>
      </Center>
    );
  }

  if (state.phase === "finished") {
    return (
      <Center>
        <p className="font-display text-2xl font-semibold">Готово, спасибо!</p>
        <a href="/course" className="mt-4 text-sm text-muted underline">
          К моему курсу
        </a>
      </Center>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col px-4 py-5">
      <div className="flex justify-between text-xs text-muted">
        <span>
          Вопрос {state.index + 1} из {state.total}
        </span>
        {state.phase === "open" && left !== null && <span className={left <= 5 ? "text-orange-300" : ""}>{left} сек</span>}
      </div>
      <p className="mt-3 font-display text-xl font-semibold leading-snug">{q.prompt}</p>

      {state.phase === "reveal" ? (
        <div className="mt-8 rounded-2xl bg-navy-900 px-5 py-6 text-center">
          {!answered ? (
            <p className="text-muted">Смотри итоги на экране</p>
          ) : state.myCorrect === true ? (
            <p className="font-display text-2xl font-semibold text-emerald-300">Верно!</p>
          ) : state.myCorrect === false ? (
            <p className="font-display text-xl font-semibold text-orange-300">Не в этот раз — смотри экран</p>
          ) : (
            <p className="font-display text-xl font-semibold text-champagne">Спасибо за ответ</p>
          )}
        </div>
      ) : (
        <>
          {q.kind === "choice" && (
            <ul className="mt-6 grid gap-3">
              {q.options.map((o, i) => {
                const chosen = state.myAnswer === i;
                return (
                  <li key={i}>
                    <button
                      type="button"
                      disabled={sending || timeUp}
                      onClick={() => answer(i)}
                      className={`flex w-full items-center gap-3 rounded-2xl px-4 py-4 text-left text-base font-semibold text-navy-950 transition disabled:opacity-60 ${
                        answered && !chosen ? "opacity-40" : ""
                      } ${chosen ? "ring-4 ring-white" : ""}`}
                      style={{ backgroundColor: OPTION_COLORS[i] }}
                    >
                      <span className="font-display">{LETTERS[i]}</span>
                      {o}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          {q.kind === "scale" && (
            <div className="mt-6 grid grid-cols-5 gap-2">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  disabled={sending || timeUp}
                  onClick={() => answer(n)}
                  className={`aspect-square rounded-2xl font-display text-2xl font-semibold disabled:opacity-60 ${
                    state.myAnswer === n ? "bg-gold-500 text-navy-950" : "bg-navy-900 text-white"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
          )}
          {q.kind === "text" && (
            <form
              className="mt-6"
              onSubmit={(e) => {
                e.preventDefault();
                if (text.trim()) answer(text);
              }}
            >
              <input
                value={text}
                onChange={(e) => setText(e.target.value)}
                maxLength={60}
                disabled={timeUp}
                placeholder="Коротко, одно-два слова"
                className="w-full rounded-xl border border-white/15 bg-navy-900 px-4 py-3 text-base text-white placeholder:text-white/30 focus:border-gold-400 focus:outline-none"
              />
              <button type="submit" disabled={sending || timeUp || !text.trim()} className="btn btn-primary mt-3 h-12 w-full disabled:opacity-50">
                {answered ? "Изменить ответ" : "Отправить"}
              </button>
            </form>
          )}
          <p className="mt-5 text-center text-sm text-muted">
            {timeUp ? "Время вышло" : answered ? "Ответ принят — можно поменять, пока вопрос открыт" : " "}
          </p>
          {error && <p className="mt-2 text-center text-sm text-red-400">{error}</p>}
        </>
      )}
    </main>
  );
}

function Center({ children }: { children: React.ReactNode }) {
  return <main className="flex flex-1 flex-col items-center justify-center px-6 text-center">{children}</main>;
}
