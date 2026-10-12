import type { LiveQuestionData, LiveSummary } from "@/lib/live";

export const LETTERS = ["A", "B", "C", "D", "E", "F"];
export const OPTION_COLORS = ["#C9A24B", "#4F8FD6", "#3DAA8A", "#D9734E", "#9B7BD4", "#C75C8A"];

/** Aggregates for the projector: bars, average, word cloud. Never names. */
export function SummaryView({ question, summary, large }: { question: LiveQuestionData; summary: LiveSummary; large?: boolean }) {
  if (summary.kind === "text") {
    if (summary.words.length === 0) return <p className="text-muted">Ответов нет</p>;
    const max = Math.max(...summary.words.map((w) => w.count));
    return (
      <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
        {summary.words.map((w, i) => (
          <span
            key={w.text}
            className="font-display font-semibold leading-tight"
            style={{
              fontSize: `${(large ? 1.1 : 0.9) + (w.count / max) * (large ? 2.4 : 1.2)}rem`,
              color: OPTION_COLORS[i % OPTION_COLORS.length]
            }}
          >
            {w.text}
          </span>
        ))}
      </div>
    );
  }

  const labels =
    summary.kind === "choice"
      ? question.options.map((o, i) => `${LETTERS[i]}  ${o}`)
      : Array.from({ length: summary.counts.length }, (_, i) => String(i + 1));
  const max = Math.max(1, ...summary.counts);
  const total = summary.counts.reduce((a, b) => a + b, 0);

  return (
    <div className="w-full">
      {summary.kind === "scale" && (
        <p className={`mb-4 text-center font-display ${large ? "text-5xl" : "text-2xl"} font-semibold text-gold-400`}>
          {summary.average ?? "—"}
          <span className={`${large ? "text-2xl" : "text-base"} text-muted`}> / 5</span>
        </p>
      )}
      <ul className="space-y-3">
        {summary.counts.map((count, i) => {
          const correct = summary.kind === "choice" && summary.correctIndex === i;
          const dim = summary.kind === "choice" && summary.correctIndex !== null && !correct;
          return (
            <li key={i} className={dim ? "opacity-45" : ""}>
              <div className={`flex justify-between gap-3 ${large ? "text-2xl" : "text-sm"}`}>
                <span className="truncate">
                  {labels[i]}
                  {correct && " ✓"}
                </span>
                <span className="text-muted">
                  {count}
                  {total > 0 && ` · ${Math.round((count / total) * 100)}%`}
                </span>
              </div>
              <div className={`mt-1 ${large ? "h-5" : "h-2"} overflow-hidden rounded-full bg-white/10`}>
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${(count / max) * 100}%`, backgroundColor: OPTION_COLORS[i % OPTION_COLORS.length] }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
