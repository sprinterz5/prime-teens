"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type Props =
  | { kind: "student"; studentId: number; label: string; redirectTo: string }
  | { kind: "mentor"; mentorId: number; label: string; redirectTo: string };

export function DevLoginButton(props: Props) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onClick() {
    setPending(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/dev-login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          props.kind === "student"
            ? { kind: "student", studentId: props.studentId }
            : { kind: "mentor", mentorId: props.mentorId }
        )
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        setError(data?.message ?? `Ошибка ${res.status}`);
        setPending(false);
        return;
      }
      router.push(props.redirectTo);
      router.refresh();
    } catch {
      setError("Сеть недоступна");
      setPending(false);
    }
  }

  return (
    <div>
      <button
        onClick={onClick}
        disabled={pending}
        className="rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10 disabled:opacity-50"
      >
        {pending ? "Вход…" : props.label}
      </button>
      {error && <p className="mt-1 text-xs text-red-400">{error}</p>}
    </div>
  );
}
