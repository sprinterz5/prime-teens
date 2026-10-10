import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";
import { loginPath } from "@/lib/auth/next-path";
import { AppHeader } from "@/components/app/app-header";
import { LiveAnswer } from "./live-answer";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Live", robots: { index: false } };

export default async function CourseLivePage() {
  const session = await getSession();
  if (!session) redirect(loginPath("/course/live"));
  if (session.role !== "student") redirect("/mentor/live");

  return (
    <div className="flex min-h-[100dvh] flex-col bg-navy-950 text-white">
      <AppHeader title="Live на уроке" backHref="/course" backLabel="Мой курс" />
      <LiveAnswer />
    </div>
  );
}
