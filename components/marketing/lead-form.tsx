"use client";

import { useState } from "react";
import { CircleCheck, LoaderCircle, User } from "lucide-react";

type FormState = "idle" | "loading" | "success" | "error";

type LeadFormProps = {
  buttonLabel?: string;
  interest?: string;
};

export function LeadForm({ buttonLabel = "Записаться", interest = "assessment" }: LeadFormProps) {
  const [state, setState] = useState<FormState>("idle");
  const [message, setMessage] = useState("");

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("loading");
    setMessage("");

    const form = event.currentTarget;
    const data = new FormData(form);

    const response = await fetch("/api/leads", {
      method: "POST",
      body: JSON.stringify({
        name: data.get("name"),
        contact: data.get("contact"),
        role: data.get("role"),
        interest,
        consent: data.get("consent") === "on",
        website: data.get("website") || ""
      }),
      headers: { "Content-Type": "application/json" }
    });

    const result = (await response.json()) as { ok: boolean; message?: string };

    if (response.ok && result.ok) {
      form.reset();
      setState("success");
      setMessage(result.message ?? "Спасибо. Мы получили заявку.");
      return;
    }

    setState("error");
    setMessage(result.message ?? "Не получилось отправить форму. Проверьте данные.");
  }

  return (
    <form onSubmit={onSubmit} className="glass rounded-lg p-5 sm:p-6">
      <div className="grid gap-3">
        <label className="sr-only" htmlFor="name">
          Имя
        </label>
        <div className="relative">
          <User className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted" size={19} aria-hidden="true" />
          <input
            id="name"
            name="name"
            type="text"
            required
            placeholder="Ваше имя"
            className="focus-ring h-12 w-full rounded-lg border border-white/[0.12] bg-white/[0.08] pl-12 pr-4 text-porcelain placeholder:text-muted"
          />
        </div>

        <label className="sr-only" htmlFor="contact">
          Телефон или email
        </label>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
          <input
            id="contact"
            name="contact"
            type="text"
            required
            placeholder="Телефон или email"
            className="focus-ring h-12 w-full rounded-lg border border-white/[0.12] bg-white/[0.08] px-4 text-porcelain placeholder:text-muted"
          />
          <button
            type="submit"
            disabled={state === "loading"}
            className="focus-ring inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-gold-500 px-5 font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {state === "loading" ? <LoaderCircle className="animate-spin" size={18} aria-hidden="true" /> : <CircleCheck size={18} aria-hidden="true" />}
            {buttonLabel}
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 text-sm text-muted sm:grid-cols-2">
        <label className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 p-3">
          <input type="radio" name="role" value="parent" defaultChecked className="accent-gold-500" />
          Я родитель
        </label>
        <label className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 p-3">
          <input type="radio" name="role" value="student" className="accent-gold-500" />
          Я студент
        </label>
      </div>

      <label className="mt-4 flex gap-3 text-xs leading-5 text-muted">
        <input type="checkbox" name="consent" required className="mt-1 accent-gold-500" />
        Согласен на обработку персональных данных и понимаю, что для студентов младше 18 лет нужно согласие родителя.
      </label>
      <input name="website" tabIndex={-1} autoComplete="off" className="hidden" aria-hidden="true" />

      {message && (
        <p className={state === "error" ? "mt-4 text-sm text-red-300" : "mt-4 text-sm text-gold-300"} role="status">
          {message}
        </p>
      )}
    </form>
  );
}
