"use client";

import { useEffect, useRef, useState } from "react";

/**
 * The token is exchanged by a POST from the browser, not on GET: Telegram and
 * messengers fetch links for previews, and a GET that burned the token would
 * log the student out of their own link before they tap it.
 */
export function LinkLogin({ token }: { token: string }) {
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token })
    })
      .then(async (res) => {
        const data = await res.json().catch(() => null);
        if (res.ok && data?.ok) window.location.replace(data.redirect);
        else setError(data?.message ?? `Ошибка ${res.status}`);
      })
      .catch(() => setError("Нет связи с сервером"));
  }, [token]);

  if (!error) return <p className="text-sm text-muted">Входим…</p>;
  return (
    <div className="max-w-sm">
      <h1 className="font-display text-xl font-semibold">Не получилось войти</h1>
      <p className="mt-3 text-sm text-muted">{error}</p>
      <a href="/login" className="btn btn-primary focus-ring mt-6 inline-flex h-11">
        Ввести код
      </a>
    </div>
  );
}
