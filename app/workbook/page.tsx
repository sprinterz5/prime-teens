import { getSession } from "@/lib/auth/session";
import { TelegramViewport } from "@/components/app/telegram-viewport";
import { TelegramAutoLogin } from "./telegram-auto-login";

export const dynamic = "force-dynamic";

function devLoginEnabled(): boolean {
  return process.env.NODE_ENV !== "production" && process.env.DEV_LOGIN === "1";
}

export default async function WorkbookPage() {
  const session = await getSession();

  if (!session || session.role !== "student") {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-navy-950 px-6 text-center text-white">
        <TelegramAutoLogin />
        <h1 className="font-display text-xl font-semibold">Откройте тетрадь через Telegram-бота</h1>
        <p className="max-w-sm text-sm text-muted">
          Рабочая тетрадь открывается из мини-приложения детского Telegram-бота PrimeTeens.
        </p>
        {devLoginEnabled() && (
          <a href="/dev/login" className="text-sm text-gold-400 underline">
            Dev-логин (только для разработки)
          </a>
        )}
      </main>
    );
  }

  return (
    <div className="flex h-[100dvh] flex-col bg-navy-950">
      <TelegramViewport />
      <TelegramAutoLogin />
      <iframe src="/workbook/frame" title="Рабочая тетрадь" className="h-full w-full border-0" />
    </div>
  );
}
