"use client";

import { useState } from "react";

const field =
  "rounded-lg border border-white/15 bg-navy-950 px-3 py-2 text-base text-white placeholder:text-white/30 focus:border-gold-400 focus:outline-none sm:text-sm";

export function AddDeadline() {
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      const res = await fetch("/api/calendar/deadlines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, date, time: time || null })
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.ok) {
        setError(data?.message ?? `Ошибка ${res.status}`);
        setPending(false);
        return;
      }
      window.location.reload();
    } catch {
      setError("Нет связи с сервером");
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-6 rounded-xl border border-white/10 bg-navy-900 p-4">
      <p className="text-sm font-semibold">Свой дедлайн</p>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        maxLength={120}
        placeholder="Например: регистрация на олимпиаду по физике"
        className={`${field} mt-3 w-full`}
      />
      <div className="mt-2 flex flex-wrap gap-2">
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={field} aria-label="Дата" />
        <input type="time" value={time} onChange={(e) => setTime(e.target.value)} className={field} aria-label="Время (необязательно)" />
        <button type="submit" disabled={pending || !title.trim() || !date} className="btn btn-primary h-10 disabled:opacity-50">
          {pending ? "Добавляем…" : "Добавить"}
        </button>
      </div>
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
    </form>
  );
}

export function DeleteDeadline({ id }: { id: number }) {
  const [pending, setPending] = useState(false);
  return (
    <button
      type="button"
      disabled={pending}
      onClick={async () => {
        if (!window.confirm("Удалить дедлайн?")) return;
        setPending(true);
        await fetch(`/api/calendar/deadlines/${id}`, { method: "DELETE" }).catch(() => null);
        window.location.reload();
      }}
      className="shrink-0 px-1 text-muted hover:text-red-300"
      aria-label="Удалить дедлайн"
    >
      ×
    </button>
  );
}

/** Subscribe link: the calendar app keeps it in sync, including new personal deadlines. */
export function Subscribe() {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function issue(rotate: boolean) {
    setError(null);
    const res = await fetch("/api/calendar/subscription", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rotate })
    }).catch(() => null);
    const data = await res?.json().catch(() => null);
    if (!data?.ok) {
      setError("Не удалось получить ссылку");
      return;
    }
    setUrl(window.location.origin + data.path);
    setCopied(false);
  }

  if (!url) {
    return (
      <div className="mt-3 text-sm">
        <button type="button" onClick={() => issue(false)} className="text-champagne underline hover:text-gold-400">
          Добавить в Google или Apple Календарь
        </button>
        {error && <p className="mt-1 text-red-400">{error}</p>}
      </div>
    );
  }

  const webcal = url.replace(/^https?:\/\//, "webcal://");
  return (
    <div className="mt-3 rounded-xl border border-white/10 bg-navy-900 p-4 text-sm">
      <div className="flex flex-wrap gap-2">
        <a
          href={`https://calendar.google.com/calendar/r?cid=${encodeURIComponent(webcal)}`}
          target="_blank"
          rel="noreferrer"
          className="btn btn-primary h-10"
        >
          Google Календарь
        </a>
        <a href={webcal} className="btn btn-secondary h-10">
          Apple / iPhone
        </a>
        <button
          type="button"
          onClick={() => navigator.clipboard?.writeText(url).then(() => setCopied(true))}
          className="btn btn-secondary h-10"
        >
          {copied ? "Скопировано" : "Скопировать ссылку"}
        </button>
      </div>
      <p className="mt-3 text-xs text-muted">
        Календарь сам подтягивает изменения. Ссылка личная — не пересылай её.{" "}
        <button type="button" onClick={() => issue(true)} className="underline hover:text-champagne">
          Выпустить новую
        </button>{" "}
        (старая перестанет работать).
      </p>
    </div>
  );
}
