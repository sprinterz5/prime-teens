"use client";

import { useCallback, useState } from "react";
import { useLiveFeed } from "@/components/live/use-live-feed";

/** "Идёт live" on the student's course pages while the group has a running session. */
export function LiveBanner() {
  const [live, setLive] = useState<{ title: string } | null>(null);

  const load = useCallback(() => {
    fetch("/api/live/current", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((s) => setLive(s?.active && s.phase !== "finished" ? { title: s.title } : null))
      .catch(() => {});
  }, []);
  useLiveFeed("/api/live/stream", load);

  if (!live) return null;
  return (
    <a
      href="/course/live"
      className="flex shrink-0 items-center justify-between gap-3 bg-gold-500 px-4 py-3 text-sm font-semibold text-navy-950"
    >
      <span className="truncate">● Идёт live: {live.title}</span>
      <span className="shrink-0">Подключиться →</span>
    </a>
  );
}
