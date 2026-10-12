"use client";

import { useEffect, useRef } from "react";

/**
 * Calls `refetch` whenever the live stream reports a change, and polls every
 * 3 s while the stream is silent (a buffering proxy) — the same fallback as
 * the mentor dashboard. Every (re)connect also refetches, so nothing missed
 * during a reconnect is lost.
 */
export function useLiveFeed(streamUrl: string, refetch: () => void) {
  const refetchRef = useRef(refetch);
  refetchRef.current = refetch;

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const update = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => refetchRef.current(), 120);
    };
    let lastLive = 0;
    const es = new EventSource(streamUrl);
    es.addEventListener("hello", () => {
      lastLive = Date.now();
      update();
    });
    es.addEventListener("ping", () => {
      lastLive = Date.now();
    });
    for (const event of ["state", "answer"]) {
      es.addEventListener(event, () => {
        lastLive = Date.now();
        update();
      });
    }
    const poll = setInterval(() => {
      if (Date.now() - lastLive > 15_000) refetchRef.current();
    }, 3_000);
    return () => {
      es.close();
      clearInterval(poll);
      if (timer) clearTimeout(timer);
    };
  }, [streamUrl]);
}

/** Seconds left on a question timer, corrected for the server/client clock offset. */
export function secondsLeft(closesAt: string | null, offsetMs: number): number | null {
  if (!closesAt) return null;
  return Math.max(0, Math.ceil((new Date(closesAt).getTime() - (Date.now() + offsetMs)) / 1000));
}
