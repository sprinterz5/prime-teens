"use client";

import { useState } from "react";

export function CodeLoginForm({ next }: { next: string | null }) {
  const [code, setCode] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code })
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.ok) {
        setError(data?.message ?? `Ошибка ${res.status}`);
        setPending(false);
        return;
      }
      window.location.replace(next ?? data.redirect);
    } catch {
      setError("Нет связи с сервером");
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mt-6">
      <label htmlFor="login-code" className="text-xs font-semibold uppercase tracking-wide text-muted">
        Код из бота
      </label>
      <input
        id="login-code"
        value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
        inputMode="numeric"
        autoComplete="one-time-code"
        placeholder="000000"
        className="mt-2 w-full rounded-lg border border-white/15 bg-navy-900 px-4 py-3 text-center font-mono text-2xl tracking-[0.5em] text-white placeholder:text-white/20 focus:border-gold-400 focus:outline-none"
      />
      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
      <button
        type="submit"
        disabled={pending || code.length !== 6}
        className="btn btn-primary focus-ring mt-4 h-12 w-full disabled:opacity-50"
      >
        {pending ? "Входим…" : "Войти"}
      </button>
    </form>
  );
}
