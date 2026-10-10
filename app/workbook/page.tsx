import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";
import { loginPath } from "@/lib/auth/next-path";
import { AppHeader } from "@/components/app/app-header";
import { TelegramViewport } from "@/components/app/telegram-viewport";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Рабочая тетрадь", robots: { index: false } };

/** The whole workbook in one scroll; day-by-day work lives at /course/day/[day]. */
export default async function WorkbookPage() {
  const session = await getSession();
  if (!session) redirect(loginPath("/workbook"));
  if (session.role !== "student") redirect("/mentor");

  return (
    <div className="flex h-[100dvh] flex-col bg-navy-950">
      <TelegramViewport />
      <AppHeader title="Рабочая тетрадь" backHref="/course" backLabel="По дням" logout />
      <iframe src="/workbook/frame" title="Рабочая тетрадь" className="min-h-0 w-full flex-1 border-0" />
    </div>
  );
}
