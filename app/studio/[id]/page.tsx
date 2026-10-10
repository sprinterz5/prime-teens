import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";
import { canEditLive } from "@/lib/auth/authorize";
import { loginPath } from "@/lib/auth/next-path";
import { AppHeader } from "@/components/app/app-header";
import { courseDaysList } from "@/lib/course";
import { ActivityEditor } from "./activity-editor";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Шаблон live-задания", robots: { index: false } };

export default async function StudioActivityPage({ params }: { params: Promise<{ id: string }> }) {
  const raw = (await params).id;
  const id = raw === "new" ? null : Number(raw);
  if (id !== null && !Number.isInteger(id)) notFound();

  const session = await getSession();
  if (!session) redirect(loginPath(`/studio/${raw}`));
  if (!canEditLive(session)) redirect(session.role === "student" ? "/course" : "/mentor");

  return (
    <div className="min-h-[100dvh] bg-navy-950 text-white">
      <AppHeader title={id === null ? "Новый шаблон" : "Шаблон live-задания"} backHref="/studio" backLabel="Все шаблоны" logout />
      <ActivityEditor id={id} days={courseDaysList.map((d) => ({ index: d.index, title: d.title }))} />
    </div>
  );
}
