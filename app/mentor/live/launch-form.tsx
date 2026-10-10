"use client";

import { useState } from "react";

type Activity = { id: number; title: string; dayIndex: number | null };

export function LaunchForm({
  groups,
  activities,
  suggestedDay
}: {
  groups: { id: number; name: string }[];
  activities: Activity[];
  suggestedDay: Record<number, number | null>;
}) {
  const [groupId, setGroupId] = useState(groups[0].id);
  const [pending, setPending] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const day = suggestedDay[groupId];
  const sorted = [...activities].sort((a, b) => Number(b.dayIndex === day) - Number(a.dayIndex === day));

  async function start(activityId: number) {
    setPending(activityId);
    setError(null);
    try {
      const res = await fetch("/api/live/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ activityId, groupId })
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.ok) {
        setError(data?.message ?? `Ошибка ${res.status}`);
        setPending(null);
        return;
      }
      window.location.href = `/live/${data.id}`;
    } catch {
      setError("Нет связи с сервером");
      setPending(null);
    }
  }

  return (
    <div className="mt-6">
      <label className="text-sm text-muted">
        Группа:{" "}
        <select
          value={groupId}
          onChange={(e) => setGroupId(Number(e.target.value))}
          className="ml-1 rounded-lg border border-white/15 bg-navy-900 px-3 py-2 text-sm text-white"
        >
          {groups.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </select>
      </label>
      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
      <ul className="mt-4 space-y-2">
        {sorted.map((a) => (
          <li key={a.id} className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-navy-900 px-4 py-3">
            <span>
              <span className="text-porcelain">{a.title}</span>
              {a.dayIndex && (
                <span className={`ml-2 text-xs ${a.dayIndex === day ? "text-gold-400" : "text-muted"}`}>
                  День {a.dayIndex}
                  {a.dayIndex === day ? " · сегодня/следующий" : ""}
                </span>
              )}
            </span>
            <button
              type="button"
              onClick={() => start(a.id)}
              disabled={pending !== null}
              className="rounded-lg bg-gold-500 px-3 py-2 text-xs font-semibold text-navy-950 disabled:opacity-50"
            >
              {pending === a.id ? "Запускаем…" : "Запустить"}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
