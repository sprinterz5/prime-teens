import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canAccessGroup } from "@/lib/auth/authorize";
import { loginPath } from "@/lib/auth/next-path";
import { AppHeader } from "@/components/app/app-header";
import { HomeworkReview } from "./homework-review";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Домашка группы", robots: { index: false } };

export default async function GroupHomeworkPage({ params }: { params: Promise<{ groupId: string }> }) {
  const groupIdRaw = (await params).groupId;
  const groupId = Number(groupIdRaw);
  if (!Number.isInteger(groupId)) notFound();

  const session = await getSession();
  if (!session) redirect(loginPath(`/mentor/groups/${groupIdRaw}/homework`));
  if (session.role === "student") redirect("/course");
  if (!(await canAccessGroup(session, groupId))) notFound();

  const group = await prisma.group.findUnique({ where: { id: groupId }, select: { name: true } });
  if (!group) notFound();

  return (
    <div className="min-h-[100dvh] bg-navy-950 text-white">
      <AppHeader title={`Домашка · ${group.name}`} backHref="/mentor" backLabel="К прогрессу" logout />
      <HomeworkReview groupId={groupId} />
    </div>
  );
}
