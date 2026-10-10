import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";
import { loginPath } from "@/lib/auth/next-path";
import { AppHeader } from "@/components/app/app-header";
import { TelegramViewport } from "@/components/app/telegram-viewport";
import { MentorDashboard } from "./mentor-dashboard";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Кабинет ментора", robots: { index: false } };

export default async function MentorPage() {
  const session = await getSession();
  if (!session) redirect(loginPath("/mentor"));
  if (session.role === "student") redirect("/course");

  return (
    <>
      <TelegramViewport />
      <AppHeader title="PrimeTeens · Кабинет ментора" logout />
      <MentorDashboard />
    </>
  );
}
