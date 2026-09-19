import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";
import { forbidden, unauthorized, visibleGroupIds } from "@/lib/auth/authorize";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const session = await getSession();
  if (!session) return unauthorized();
  if (session.role === "student") return forbidden();

  const groups = await visibleGroupIds(session);
  const rows = await prisma.group.findMany({
    where: groups === "all" ? {} : { id: { in: groups } },
    orderBy: { name: "asc" },
    select: {
      id: true,
      name: true,
      startDate: true,
      shift: true,
      format: true,
      lessonTime: true,
      archivedAt: true,
      endsAt: true
    }
  });

  return NextResponse.json({ isAdmin: session.role === "admin", groups: rows });
}
