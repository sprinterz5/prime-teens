import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { canAccessGroup, forbidden, unauthorized } from "@/lib/auth/authorize";
import { groupRisk } from "@/lib/risk";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_request: Request, { params }: { params: Promise<{ groupId: string }> }) {
  const session = await getSession();
  if (!session) return unauthorized();
  if (session.role === "student") return forbidden();
  const groupId = Number((await params).groupId);
  if (!Number.isInteger(groupId)) return NextResponse.json({ ok: false, message: "Некорректный groupId" }, { status: 400 });
  if (!(await canAccessGroup(session, groupId))) return forbidden();
  return NextResponse.json(await groupRisk(groupId));
}
