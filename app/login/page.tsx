import type { Metadata } from "next";
import Image from "next/image";
import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";
import { homePath } from "@/lib/auth/login-code";
import { safeNextPath } from "@/lib/auth/next-path";
import { TelegramAutoLogin } from "@/app/workbook/telegram-auto-login";
import { CodeLoginForm } from "./code-login-form";

export const dynamic = "force-dynamic";

function devLoginEnabled(): boolean {
  return process.env.NODE_ENV !== "production" && process.env.DEV_LOGIN === "1";
}
export const metadata: Metadata = { title: "Вход на платформу", robots: { index: false } };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string | string[] }> }) {
  const next = safeNextPath((await searchParams).next);
  const session = await getSession();
  if (session) redirect(next ?? homePath(session));

  return (
    <main className="flex min-h-[100dvh] items-center justify-center bg-navy-950 px-4 py-10 text-white">
      {/* Opened from an old Mini App button inside Telegram: still logs in silently. */}
      <TelegramAutoLogin />
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-3">
          <Image src="/prime-teens-logo.png" alt="" width={40} height={40} className="h-10 w-10 rounded-lg object-cover" />
          <div className="font-display text-lg font-semibold text-porcelain">PrimeTeens</div>
        </div>

        <h1 className="mt-8 font-display text-2xl font-semibold">Вход на платформу</h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          Отправьте <span className="font-mono text-champagne">/login</span> своему боту PrimeTeens: ученики — детскому,
          менторы — менторскому. Бот пришлёт ссылку для входа и код.
        </p>

        <CodeLoginForm next={next} />

        <p className="mt-6 text-xs leading-5 text-muted">
          Ссылка и код одноразовые и действуют 15 минут. Ссылку удобнее открыть на телефоне, код — ввести на компьютере.
        </p>
        {devLoginEnabled() && (
          <a href="/dev/login" className="mt-4 inline-block text-sm text-gold-400 underline">
            Dev-логин (только для разработки)
          </a>
        )}
      </div>
    </main>
  );
}
