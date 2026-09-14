"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

type Group = {
  id: number;
  name: string;
  startDate: string | null;
  shift: string;
  format: string | null;
  lessonTime: string | null;
};

type StudentProgress = {
  id: number;
  fullName: string;
  shortName: string | null;
  filledByDay: Record<string, number>;
  percentByDay: Record<string, number>;
  lastActivity: string | null;
};

type Progress = {
  days: number[];
  totalsByDay: Record<string, number>;
  students: StudentProgress[];
};

function percentColor(pct: number): string {
  // 0% -> muted red, 100% -> brand gold/green. Simple HSL ramp.
  const hue = 0 + (pct / 100) * 130; // 0 red -> 130 green
  return `hsl(${hue}, 55%, 32%)`;
}

function formatLastActivity(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function MentorDashboard() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [groupId, setGroupId] = useState<number | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const refetchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    fetch("/api/mentor/groups")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data) => {
        setGroups(data.groups);
        if (data.groups.length > 0) setGroupId(data.groups[0].id);
      })
      .catch(() => setError("Не удалось загрузить группы"));
  }, []);

  const loadProgress = useCallback((id: number) => {
    fetch(`/api/mentor/groups/${id}/progress`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setProgress)
      .catch(() => setError("Не удалось загрузить прогресс группы"));
  }, []);

  useEffect(() => {
    if (groupId === null) return;
    setProgress(null);
    loadProgress(groupId);

    esRef.current?.close();
    const es = new EventSource(`/api/mentor/groups/${groupId}/stream`);
    esRef.current = es;
    const onUpdate = () => {
      // Any entry/drawing change in the group: refetch progress, debounced.
      if (refetchTimer.current) clearTimeout(refetchTimer.current);
      refetchTimer.current = setTimeout(() => loadProgress(groupId), 300);
    };
    // If a proxy buffers the stream (no hello/ping for 15 s), poll instead.
    let lastLive = 0;
    const markLive = () => {
      lastLive = Date.now();
    };
    es.addEventListener("hello", () => {
      markLive();
      onUpdate(); // catch up on anything missed while (re)connecting
    });
    es.addEventListener("ping", markLive);
    es.addEventListener("entry", () => {
      markLive();
      onUpdate();
    });
    es.addEventListener("drawing", () => {
      markLive();
      onUpdate();
    });
    const poll = setInterval(() => {
      if (Date.now() - lastLive > 15_000) loadProgress(groupId);
    }, 5_000);

    return () => {
      es.close();
      clearInterval(poll);
      if (refetchTimer.current) clearTimeout(refetchTimer.current);
    };
  }, [groupId, loadProgress]);

  return (
    <main className="min-h-screen bg-navy-950 px-4 py-8 text-white sm:px-8">
      <h1 className="font-display text-2xl font-semibold">Прогресс учеников</h1>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <label className="text-sm text-muted" htmlFor="group-select">
          Группа:
        </label>
        <select
          id="group-select"
          value={groupId ?? ""}
          onChange={(e) => setGroupId(Number(e.target.value))}
          className="rounded-lg border border-white/15 bg-navy-900 px-3 py-2 text-sm text-white"
        >
          {groups.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="mt-4 text-sm text-red-400">{error}</p>}

      {progress && (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-white/10 text-left text-muted">
                <th className="py-2 pr-4">Ученик</th>
                {progress.days.map((day) => (
                  <th key={day} className="px-2 py-2 text-center">
                    День {day}
                  </th>
                ))}
                <th className="px-2 py-2 text-right">Активность</th>
              </tr>
            </thead>
            <tbody>
              {progress.students.map((s) => (
                <tr key={s.id} className="border-b border-white/5">
                  <td className="py-2 pr-4">
                    <Link href={`/mentor/students/${s.id}`} className="underline hover:text-gold-400">
                      {s.shortName ?? s.fullName}
                    </Link>
                  </td>
                  {progress.days.map((day) => {
                    const pct = s.percentByDay[String(day)] ?? s.percentByDay[day] ?? 0;
                    return (
                      <td key={day} className="px-2 py-2 text-center">
                        <span
                          className="inline-block min-w-[3rem] rounded px-2 py-1 text-xs font-semibold"
                          style={{ backgroundColor: percentColor(pct) }}
                        >
                          {pct}%
                        </span>
                      </td>
                    );
                  })}
                  <td className="px-2 py-2 text-right text-muted">{formatLastActivity(s.lastActivity)}</td>
                </tr>
              ))}
              {progress.students.length === 0 && (
                <tr>
                  <td colSpan={progress.days.length + 2} className="py-6 text-center text-muted">
                    В группе нет учеников
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
