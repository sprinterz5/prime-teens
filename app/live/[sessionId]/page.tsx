import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { canRunLive } from "@/lib/auth/authorize";
import { loginPath } from "@/lib/auth/next-path";
import { Presenter } from "./presenter";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Live · экран ведущего", robots: { index: false } };

export default async function LivePresenterPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const raw = (await params).sessionId;
  const id = Number(raw);
  if (!Number.isInteger(id)) notFound();

  const session = await getSession();
  if (!session) redirect(loginPath(`/live/${raw}`));
  if (session.role === "student") redirect("/course/live");

  const live = await prisma.liveSession.findUnique({ where: { id }, select: { groupId: true } });
  if (!live || !(await canRunLive(session, live.groupId))) notFound();

  const site = (process.env.NEXT_PUBLIC_SITE_URL ?? "").replace(/^https?:\/\//, "").replace(/\/$/, "");
  return <Presenter id={id} joinHint={`${site || "сайт PrimeTeens"}/course`} />;
}
