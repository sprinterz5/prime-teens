import { randomUUID } from "node:crypto";
import { mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Used by the monitoring script (deploy/monitor/monitor.sh) and, optionally,
// an external uptime checker. No auth, no PII, no version/secret leakage -
// just "can this process talk to Postgres and write to disk".
export async function GET() {
  const failed: string[] = [];

  try {
    await prisma.$queryRaw`SELECT 1`;
  } catch {
    failed.push("database");
  }

  try {
    const dir = path.join(process.cwd(), "storage");
    await mkdir(dir, { recursive: true });
    const probePath = path.join(dir, `.health-${randomUUID()}.tmp`);
    await writeFile(probePath, "ok");
    await rm(probePath, { force: true });
  } catch {
    failed.push("storage");
  }

  if (failed.length > 0) {
    return NextResponse.json({ ok: false, failed }, { status: 503 });
  }
  return NextResponse.json({ ok: true });
}
