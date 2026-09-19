/**
 * Nightly housekeeping for every already-archived group: converts any
 * drawing still stored as PNG to WebP, and exports any student PDF that
 * doesn't exist yet. Meant to run unattended (systemd timer — see deploy/)
 * as `pnpm archive:pending`, separate from the admin "Завершить поток"
 * button (which only does the lock + WebP synchronously — see
 * app/api/admin/groups/[groupId]/archive/route.ts) so PDF export (slow,
 * Playwright/Chromium) never blocks that click.
 *
 * Idempotent by construction: both convertGroupDrawingsToWebp (skips rows
 * already .webp) and exportGroupPdfs (skips a PDF that already exists) are
 * no-ops on anything already done, so running this every night against every
 * archived group — not just recently-archived ones — is cheap and safe.
 *
 * Usage: pnpm archive:pending
 */
import { prisma } from "@/lib/prisma";
import { convertGroupDrawingsToWebp } from "@/lib/workbook/archive";
import { exportGroupPdfs } from "@/lib/workbook/export-pdf";

function baseUrl(): string {
  return process.env.ARCHIVE_BASE_URL || process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
}

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

async function main() {
  const groups = await prisma.group.findMany({
    where: { archivedAt: { not: null } },
    select: { id: true, name: true },
    orderBy: { name: "asc" }
  });

  if (groups.length === 0) {
    console.log("Запертых групп нет — нечего делать.");
    await prisma.$disconnect();
    return;
  }

  console.log(`Запертых групп: ${groups.length}`);
  let totalConverted = 0;
  let totalPdfCreated = 0;

  for (const group of groups) {
    const students = await prisma.student.findMany({
      where: { groupId: group.id },
      select: { id: true, fullName: true },
      orderBy: { fullName: "asc" }
    });

    console.log(`\n== ${group.name} (id=${group.id}), учеников: ${students.length} ==`);

    const webp = await convertGroupDrawingsToWebp(group.id);
    totalConverted += webp.converted;
    if (webp.converted > 0) {
      console.log(
        `  WebP: сконвертировано ${webp.converted} | ${fmtBytes(webp.bytesBefore)} -> ${fmtBytes(webp.bytesAfter)}`
      );
    } else {
      console.log("  WebP: всё уже сконвертировано");
    }

    const pdfs = await exportGroupPdfs(baseUrl(), group.id, students);
    const created = pdfs.filter((p) => !p.skipped);
    totalPdfCreated += created.length;
    console.log(`  PDF: создано ${created.length}, уже было ${pdfs.length - created.length}`);
    for (const p of created) console.log(`    + ${p.relPath} (${fmtBytes(p.bytes)})`);
  }

  console.log(`\nИтого: WebP-конвертаций ${totalConverted}, новых PDF ${totalPdfCreated}`);
  await prisma.$disconnect();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
