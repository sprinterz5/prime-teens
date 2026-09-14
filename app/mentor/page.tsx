import { getSession } from "@/lib/auth/session";
import { MentorDashboard } from "./mentor-dashboard";

export const dynamic = "force-dynamic";

function devLoginEnabled(): boolean {
  return process.env.NODE_ENV !== "production" && process.env.DEV_LOGIN === "1";
}

export default async function MentorPage() {
  const session = await getSession();

  if (!session || session.role === "student") {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-navy-950 px-6 text-center text-white">
        <h1 className="font-display text-xl font-semibold">Только для менторов и админов</h1>
        <p className="max-w-sm text-sm text-muted">Войдите как ментор через Telegram-бота.</p>
        {devLoginEnabled() && (
          <a href="/dev/login" className="text-sm text-gold-400 underline">
            Dev-логин (только для разработки)
          </a>
        )}
      </main>
    );
  }

  return <MentorDashboard />;
}
